"""Sincronização manual com a Gmail API (roda em thread; não toca na interface).

Fluxo: perfil -> (histórico incremental | carga inicial) -> detalhes -> classifica
-> grava no SQLite. O historyId só é salvo ao final com sucesso, então uma falha
no meio nunca "pula" mensagens: a próxima tentativa recomeça do ponto anterior.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from src.mail.email_processor import process_message
from src.mail.gmail_api import GmailClient, HistoryExpired, NotFound

log = logging.getLogger(__name__)

INITIAL_LIMIT = 50    # mensagens baixadas na primeira sincronização (economiza cota)
WORKERS = 2           # downloads paralelos (bem abaixo do limite por usuário do Gmail)


@dataclass
class SyncResult:
    account_email: str
    added: int = 0
    deleted: int = 0
    full: bool = False


class SyncService:
    def __init__(self, db, client: GmailClient, progress=None,
                 initial_limit: int = INITIAL_LIMIT):
        self.db = db
        self.client = client
        self.progress = progress or (lambda text: None)
        self.initial_limit = initial_limit

    def run(self) -> SyncResult:
        self.progress("Verificando conta…")
        profile = self.client.get_profile()
        email = profile["emailAddress"]
        account_id = self.db.upsert_account(email)
        state = self.db.get_sync_state(account_id)
        result = SyncResult(email)

        if state.history_id:
            try:
                self._incremental(account_id, state.history_id, result)
                self._reconcile_read(account_id)
                return result
            except HistoryExpired:
                log.warning("historyId expirado; sincronização completa")
                self.db.reset_history(account_id)
        self._full(account_id, profile["historyId"], result)
        self._reconcile_read(account_id)
        return result

    def _reconcile_read(self, account_id):
        """Garante que lido/não lido reflita o Gmail (o histórico sozinho não basta)."""
        try:
            unread = self.client.list_inbox_ids(self.initial_limit, unread_only=True)
            self.db.reconcile_read_state(account_id, unread, len(unread) < self.initial_limit)
        except Exception:
            log.warning("Não foi possível conciliar o estado de leitura", exc_info=True)

    # ------------------------------------------------------------ completa
    def _full(self, account_id, history_id, result):
        result.full = True
        self.progress("Listando mensagens…")
        ids = self.client.list_inbox_ids(self.initial_limit)
        result.added = self._download(account_id, ids)
        # historyId lido ANTES da listagem: mudanças durante o download não se perdem.
        self.db.save_sync_state(account_id, history_id)

    # ---------------------------------------------------------- incremental
    def _incremental(self, account_id, history_id, result):
        self.progress("Buscando mensagens novas…")
        records, latest = self.client.list_history(history_id)
        added, deleted, read_changes = [], set(), {}
        for rec in records:
            for item in rec.get("messagesAdded", []):
                added.append(item["message"]["id"])
            for item in rec.get("messagesDeleted", []):
                deleted.add(item["message"]["id"])
            for key, is_read in (("labelsAdded", False), ("labelsRemoved", True)):
                for item in rec.get(key, []):
                    if "UNREAD" in item.get("labelIds", []):
                        read_changes[item["message"]["id"]] = is_read
        if deleted:
            result.deleted = self.db.delete_messages(account_id, list(deleted))
        result.added = self._download(account_id, [i for i in dict.fromkeys(added) if i not in deleted])
        for gmail_id, is_read in read_changes.items():
            self.db.update_read_state(account_id, gmail_id, is_read)
        self.db.save_sync_state(account_id, latest)

    # ------------------------------------------------------------- download
    def _download(self, account_id, ids) -> int:
        known = self.db.known_gmail_ids(account_id, ids)
        todo = [i for i in ids if i not in known]
        if not todo:
            return 0
        total, done, inserted = len(todo), 0, 0
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for start in range(0, total, 20):  # lotes: grava aos poucos e informa progresso
                batch = todo[start:start + 20]
                messages = [m for m in pool.map(self._fetch, batch) if m]
                inserted += self.db.insert_messages(account_id, messages)
                done += len(batch)
                self.progress(f"Baixando mensagens… {done}/{total}")
        return inserted

    def _fetch(self, gmail_id):
        try:
            return process_message(self.client.get_message(gmail_id))
        except NotFound:
            return None  # apagada entre a listagem e a leitura
