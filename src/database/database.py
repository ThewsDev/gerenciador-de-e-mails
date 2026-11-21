"""Camada de acesso ao SQLite local (contas, mensagens e estado de sincronização).

Responsabilidades:
- criar o banco e aplicar migrações (PRAGMA user_version) na primeira execução;
- inserir mensagens sem duplicar (UNIQUE(account_id, gmail_id));
- consultar, filtrar e pesquisar localmente (texto sem acento/caixa);
- guardar o `historyId` da Gmail API para sincronização incremental.

Não contém regras de classificação nem código de interface.

Concorrência: cada operação abre sua própria conexão (barata no SQLite) e usa
WAL, então a thread de sincronização (Etapa 7) pode gravar enquanto a interface lê.
"""
import logging
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from src.config import settings
from src.mail.email_normalizer import NormalizedMessage
from src.utils.dates import now_ms
from src.utils.text import collapse_whitespace, normalize_text, split_terms

log = logging.getLogger(__name__)

# Limite conservador de variáveis por consulta (SQLite antigo: 999).
_MAX_SQL_VARS = 500

# Cada item é uma migração; o índice + 1 é o valor de user_version resultante.
_MIGRATIONS = [
    """
    CREATE TABLE accounts (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        email         TEXT    NOT NULL UNIQUE,
        history_id    TEXT,               -- último historyId sincronizado (Gmail)
        last_sync_at  INTEGER,            -- epoch ms da última sincronização completa
        created_at    INTEGER NOT NULL
    );

    CREATE TABLE messages (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id    INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        gmail_id      TEXT    NOT NULL,
        thread_id     TEXT,
        sender_name   TEXT    NOT NULL DEFAULT '',
        sender_email  TEXT    NOT NULL DEFAULT '',
        subject       TEXT    NOT NULL DEFAULT '',
        snippet       TEXT    NOT NULL DEFAULT '',
        body          TEXT    NOT NULL DEFAULT '',
        internal_date INTEGER NOT NULL,   -- epoch ms (UTC)
        category      TEXT    NOT NULL DEFAULT 'Outros',
        is_read       INTEGER NOT NULL DEFAULT 1,
        -- colunas normalizadas (sem acento/caixa) usadas apenas pela pesquisa
        sender_norm   TEXT    NOT NULL DEFAULT '',
        subject_norm  TEXT    NOT NULL DEFAULT '',
        search_text   TEXT    NOT NULL DEFAULT '',
        created_at    INTEGER NOT NULL,
        UNIQUE (account_id, gmail_id)
    );

    CREATE INDEX idx_messages_date          ON messages (internal_date DESC);
    CREATE INDEX idx_messages_category_date ON messages (category, internal_date DESC);
    CREATE INDEX idx_messages_account_date  ON messages (account_id, internal_date DESC);
    CREATE INDEX idx_messages_unread        ON messages (internal_date DESC) WHERE is_read = 0;
    """,
]

# Colunas da listagem: sem `body` nem colunas de busca, para listas leves.
_LIST_COLUMNS = (
    "id, account_id, gmail_id, thread_id, sender_name, sender_email, subject, "
    "snippet, internal_date, category, is_read"
)


@dataclass
class MessageQuery:
    """Filtros combináveis (AND). Campos vazios são ignorados."""
    text: str = ""                       # palavras-chave: remetente, assunto ou conteúdo
    sender: str = ""                     # nome ou e-mail do remetente
    subject: str = ""
    category: Optional[str] = None
    date_from_ms: Optional[int] = None   # inclusivo
    date_to_ms: Optional[int] = None     # exclusivo
    unread_only: bool = False
    account_id: Optional[int] = None


@dataclass
class SyncState:
    history_id: Optional[str]
    last_sync_at: Optional[int]


def _like(term: str) -> str:
    """Padrão LIKE '%termo%' com curingas do usuário escapados (use ESCAPE '\\')."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _chunks(items: Sequence, size: int = _MAX_SQL_VARS):
    for start in range(0, len(items), size):
        yield items[start:start + size]


class Database:
    def __init__(self, path: str):
        self.path = path

    # ------------------------------------------------------------------ setup
    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        """Cria o arquivo/tabelas na primeira execução e aplica migrações pendentes."""
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > len(_MIGRATIONS):
                raise RuntimeError(
                    f"Banco mais novo (v{version}) que o aplicativo (v{len(_MIGRATIONS)})."
                )
            for target, script in enumerate(_MIGRATIONS, start=1):
                if target <= version:
                    continue
                log.info("Aplicando migração do banco v%d", target)
                conn.executescript(script)
                conn.execute(f"PRAGMA user_version = {target}")

    def schema_version(self) -> int:
        with self._connect() as conn:
            return conn.execute("PRAGMA user_version").fetchone()[0]

    # --------------------------------------------------------------- contas
    def upsert_account(self, email: str) -> int:
        """Retorna o id da conta, criando-a se necessário."""
        email = (email or "").strip().lower()
        if not email:
            raise ValueError("E-mail da conta é obrigatório.")
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO accounts (email, created_at) VALUES (?, ?)",
                (email, now_ms()),
            )
            row = conn.execute("SELECT id FROM accounts WHERE email = ?", (email,)).fetchone()
            return row["id"]

    def list_accounts(self) -> List[dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT id, email, history_id, last_sync_at, created_at FROM accounts ORDER BY id")]

    def get_account_id(self, email: str) -> Optional[int]:
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM accounts WHERE email = ?",
                               ((email or "").strip().lower(),)).fetchone()
            return row["id"] if row else None

    def remove_account(self, email: str) -> int:
        """Remove a conta e, em cascata, todas as suas mensagens. Retorna nº de contas removidas."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM accounts WHERE email = ?",
                               ((email or "").strip().lower(),))
            return cur.rowcount

    # --------------------------------------------------- estado de sincronização
    def get_sync_state(self, account_id: int) -> SyncState:
        with self._connect() as conn:
            row = conn.execute("SELECT history_id, last_sync_at FROM accounts WHERE id = ?",
                               (account_id,)).fetchone()
        if row is None:
            raise KeyError(f"Conta {account_id} não existe.")
        return SyncState(row["history_id"], row["last_sync_at"])

    def save_sync_state(self, account_id: int, history_id: Optional[str],
                        synced_at_ms: Optional[int] = None) -> None:
        """Grava o historyId e o instante da sincronização (padrão: agora)."""
        with self._connect() as conn:
            conn.execute("UPDATE accounts SET history_id = ?, last_sync_at = ? WHERE id = ?",
                         (history_id, synced_at_ms or now_ms(), account_id))

    def reset_history(self, account_id: int) -> None:
        """Descarta o historyId (ex.: HTTP 404 do history.list) para forçar sync completa."""
        with self._connect() as conn:
            conn.execute("UPDATE accounts SET history_id = NULL WHERE id = ?", (account_id,))

    def last_sync_at(self) -> Optional[int]:
        with self._connect() as conn:
            return conn.execute("SELECT MAX(last_sync_at) FROM accounts").fetchone()[0]

    # ------------------------------------------------------------- escrita
    def insert_messages(self, account_id: int, messages: Iterable[NormalizedMessage]) -> int:
        """Insere mensagens novas numa única transação; ignora as já existentes.

        Retorna quantas foram realmente inseridas. A prevenção de duplicatas é
        garantida pela restrição UNIQUE(account_id, gmail_id), não só pela aplicação.
        """
        inserted = 0
        created = now_ms()
        with self._connect() as conn:
            for msg in messages:
                if not msg.gmail_id:
                    raise ValueError("Mensagem sem gmail_id.")
                body = (msg.body or "")[:settings.MAX_BODY_CHARS]
                snippet = collapse_whitespace(msg.snippet or body, settings.MAX_SNIPPET_CHARS)
                name = (msg.sender_name or "").strip()
                address = (msg.sender_email or "").strip().lower()
                subject = (msg.subject or "").strip()
                search_text = normalize_text(f"{name} {address} {subject} {body}")
                cur = conn.execute(
                    """INSERT OR IGNORE INTO messages
                       (account_id, gmail_id, thread_id, sender_name, sender_email, subject,
                        snippet, body, internal_date, category, is_read,
                        sender_norm, subject_norm, search_text, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (account_id, msg.gmail_id, msg.thread_id, name, address, subject,
                     snippet, body, int(msg.internal_date_ms),
                     msg.category or settings.DEFAULT_CATEGORY, 1 if msg.is_read else 0,
                     normalize_text(f"{name} {address}"), normalize_text(subject),
                     search_text[:settings.MAX_SEARCH_CHARS], created),
                )
                inserted += cur.rowcount
        return inserted

    def known_gmail_ids(self, account_id: int, gmail_ids: Sequence[str]) -> set:
        """Subconjunto de `gmail_ids` já armazenado — evita baixar de novo."""
        known = set()
        ids = list(gmail_ids)
        with self._connect() as conn:
            for chunk in _chunks(ids):
                marks = ",".join("?" * len(chunk))
                rows = conn.execute(
                    f"SELECT gmail_id FROM messages WHERE account_id = ? AND gmail_id IN ({marks})",
                    [account_id, *chunk])
                known.update(r["gmail_id"] for r in rows)
        return known

    def update_read_state(self, account_id: int, gmail_id: str, is_read: bool) -> bool:
        """Reflete mudança de rótulo UNREAD vinda do histórico. True se a mensagem existe."""
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE messages SET is_read = ? WHERE account_id = ? AND gmail_id = ?",
                (1 if is_read else 0, account_id, gmail_id))
            return cur.rowcount > 0

    def mark_read(self, message_id: int) -> None:
        """Marca como lida localmente (o app só tem permissão de leitura no Gmail)."""
        with self._connect() as conn:
            conn.execute("UPDATE messages SET is_read = 1 WHERE id = ? AND is_read = 0",
                         (message_id,))

    def reconcile_read_state(self, account_id: int, unread_ids: Sequence[str],
                             complete: bool) -> None:
        """Alinha is_read com o Gmail: `unread_ids` são os não lidos da caixa de entrada.

        Com `complete=False` (lista truncada) só marca como não lidas, sem marcar lidas.
        """
        unread = set(unread_ids)
        with self._connect() as conn:
            rows = conn.execute("SELECT gmail_id, is_read FROM messages WHERE account_id = ?",
                                (account_id,)).fetchall()
            to_unread = []  # leituras feitas no app não devem voltar a "não lido"
            to_read = ([r["gmail_id"] for r in rows
                        if not r["is_read"] and r["gmail_id"] not in unread] if complete else [])
            for value, ids in ((0, to_unread), (1, to_read)):
                for chunk in _chunks(ids):
                    marks = ",".join("?" * len(chunk))
                    conn.execute(
                        f"UPDATE messages SET is_read = ? WHERE account_id = ? AND gmail_id IN ({marks})",
                        [value, account_id, *chunk])

    def delete_messages(self, account_id: int, gmail_ids: Sequence[str]) -> int:
        """Remove mensagens apagadas no Gmail (messagesDeleted do history.list)."""
        removed = 0
        with self._connect() as conn:
            for chunk in _chunks(list(gmail_ids)):
                marks = ",".join("?" * len(chunk))
                cur = conn.execute(
                    f"DELETE FROM messages WHERE account_id = ? AND gmail_id IN ({marks})",
                    [account_id, *chunk])
                removed += cur.rowcount
        return removed

    def update_categories(self, pairs: Iterable[tuple]) -> int:
        """Atualiza categorias em lote: pairs = [(message_id, categoria), ...]."""
        data = [(cat, mid) for mid, cat in pairs]
        with self._connect() as conn:
            cur = conn.executemany("UPDATE messages SET category = ? WHERE id = ?", data)
            return cur.rowcount

    def clear_messages(self, account_id: Optional[int] = None) -> int:
        """Apaga mensagens locais (mantém contas e, portanto, o vínculo de login).

        O historyId é descartado: sem mensagens locais, a próxima sync deve ser completa.
        """
        with self._connect() as conn:
            if account_id is None:
                cur = conn.execute("DELETE FROM messages")
                conn.execute("UPDATE accounts SET history_id = NULL, last_sync_at = NULL")
            else:
                cur = conn.execute("DELETE FROM messages WHERE account_id = ?", (account_id,))
                conn.execute("UPDATE accounts SET history_id = NULL, last_sync_at = NULL WHERE id = ?",
                             (account_id,))
            return cur.rowcount

    # ------------------------------------------------------------- leitura
    @staticmethod
    def _where(q: MessageQuery):
        clauses, params = [], []
        if q.account_id is not None:
            clauses.append("account_id = ?")
            params.append(q.account_id)
        if q.category:
            clauses.append("category = ?")
            params.append(q.category)
        if q.unread_only:
            clauses.append("is_read = 0")
        if q.date_from_ms is not None:
            clauses.append("internal_date >= ?")
            params.append(int(q.date_from_ms))
        if q.date_to_ms is not None:
            clauses.append("internal_date < ?")
            params.append(int(q.date_to_ms))
        for column, raw in (("search_text", q.text), ("sender_norm", q.sender),
                            ("subject_norm", q.subject)):
            for term in split_terms(raw):
                clauses.append(f"{column} LIKE ? ESCAPE '\\'")
                params.append(_like(term))
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    @staticmethod
    def _to_dict(row: sqlite3.Row) -> dict:
        data = dict(row)
        data["is_read"] = bool(data["is_read"])
        return data

    def search(self, query: Optional[MessageQuery] = None, limit: int = 50,
               offset: int = 0) -> List[dict]:
        """Mensagens (mais recentes primeiro) que atendem a todos os filtros, sem o corpo."""
        where, params = self._where(query or MessageQuery())
        sql = (f"SELECT {_LIST_COLUMNS} FROM messages{where} "
               "ORDER BY internal_date DESC, id DESC LIMIT ? OFFSET ?")
        with self._connect() as conn:
            return [self._to_dict(r) for r in conn.execute(sql, [*params, limit, offset])]

    def count(self, query: Optional[MessageQuery] = None) -> int:
        where, params = self._where(query or MessageQuery())
        with self._connect() as conn:
            return conn.execute(f"SELECT COUNT(*) FROM messages{where}", params).fetchone()[0]

    def count_by_category(self, account_id: Optional[int] = None) -> dict:
        """{categoria: quantidade}; só inclui categorias que têm mensagens."""
        sql = "SELECT category, COUNT(*) AS n FROM messages"
        params: list = []
        if account_id is not None:
            sql += " WHERE account_id = ?"
            params.append(account_id)
        sql += " GROUP BY category"
        with self._connect() as conn:
            return {r["category"]: r["n"] for r in conn.execute(sql, params)}

    def get_message(self, message_id: int) -> Optional[dict]:
        """Mensagem completa (com corpo) pelo id local."""
        with self._connect() as conn:
            row = conn.execute(f"SELECT {_LIST_COLUMNS}, body FROM messages WHERE id = ?",
                               (message_id,)).fetchone()
        return self._to_dict(row) if row else None

    def iter_for_classification(self, batch_size: int = 200):
        """Gera lotes (id, remetente, assunto, corpo) para reclassificar tudo (Etapa 6)."""
        last_id = 0
        while True:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, sender_name, sender_email, subject, body FROM messages "
                    "WHERE id > ? ORDER BY id LIMIT ?", (last_id, batch_size)).fetchall()
            if not rows:
                return
            last_id = rows[-1]["id"]
            yield [dict(r) for r in rows]

    # ------------------------------------------------------------ manutenção
    def size_bytes(self) -> int:
        """Bytes de dados em uso (páginas ocupadas); o arquivo/WAL em disco não encolhe."""
        with self._connect() as conn:
            pages = conn.execute("PRAGMA page_count").fetchone()[0]
            free = conn.execute("PRAGMA freelist_count").fetchone()[0]
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        return max(pages - free, 0) * page_size

    def vacuum(self) -> None:
        with self._connect() as conn:
            conn.commit()  # VACUUM não pode rodar dentro de transação
            conn.execute("VACUUM")
