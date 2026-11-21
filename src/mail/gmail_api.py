"""Cliente REST mínimo da Gmail API (somente leitura, sempre sobre HTTPS).

Usa o access token obtido pelo Google Identity Services. Faz paginação, repete
chamadas em caso de limite de taxa/erro temporário e traduz erros em exceções
que o serviço de sincronização sabe tratar.
"""
import logging
import time

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"
TIMEOUT = 20
MAX_RETRIES = 3


class GmailError(Exception):
    """Falha genérica da Gmail API ou de rede."""


class AuthError(GmailError):
    """Token ausente, expirado ou revogado (HTTP 401/403 de permissão)."""


class HistoryExpired(GmailError):
    """historyId antigo demais (HTTP 404): é preciso sincronizar tudo de novo."""


class NotFound(GmailError):
    """Mensagem inexistente (apagada entre a listagem e a leitura)."""


class GmailClient:
    def __init__(self, access_token: str, session=None):
        if not access_token:
            raise AuthError("Sem token de acesso.")
        self._headers = {"Authorization": f"Bearer {access_token}"}
        self._http = session or requests

    # ------------------------------------------------------------- núcleo
    def _get(self, path: str, params=None) -> dict:
        url = f"{BASE_URL}/{path}"
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._http.get(url, headers=self._headers, params=params, timeout=TIMEOUT)
            except requests.RequestException as exc:
                if attempt == MAX_RETRIES:
                    raise GmailError("Sem conexão com o Gmail. Verifique a internet.") from exc
                time.sleep(2 ** attempt)
                continue

            status = resp.status_code
            if status == 200:
                return resp.json()
            if status == 401:
                raise AuthError("Autorização expirada.")
            if status == 404:
                raise NotFound(path)
            reason = self._reason(resp)
            retryable = status in (429, 500, 502, 503, 504) or (
                status == 403 and reason in ("rateLimitExceeded", "userRateLimitExceeded"))
            if retryable and attempt < MAX_RETRIES:
                wait = self._retry_after(resp) or 2 ** attempt
                log.warning("Gmail %s (%s); nova tentativa em %ss", status, reason, wait)
                time.sleep(min(wait, 30))
                continue
            if retryable:
                raise GmailError("Limite de uso da Gmail API atingido. Aguarde um minuto e tente de novo.")
            if status == 403:
                raise AuthError("Permissão negada pelo Google.")
            raise GmailError(f"Erro {status} da Gmail API ({reason or 'desconhecido'}).")
        raise GmailError("Falha inesperada ao consultar a Gmail API.")  # pragma: no cover

    @staticmethod
    def _reason(resp) -> str:
        try:
            return resp.json()["error"]["errors"][0]["reason"]
        except Exception:
            return ""

    @staticmethod
    def _retry_after(resp):
        try:
            return float(resp.headers.get("Retry-After", ""))
        except ValueError:
            return None

    # ---------------------------------------------------------- endpoints
    def get_profile(self) -> dict:
        """{'emailAddress', 'historyId', ...}"""
        return self._get("profile")

    def list_inbox_ids(self, limit: int, unread_only: bool = False):
        """IDs da caixa de entrada, mais recentes primeiro, até `limit` (paginado)."""
        ids, token = [], None
        while len(ids) < limit:
            params = {"labelIds": ["INBOX", "UNREAD"] if unread_only else "INBOX",
                      "maxResults": min(100, limit - len(ids))}
            if token:
                params["pageToken"] = token
            data = self._get("messages", params)
            ids.extend(m["id"] for m in data.get("messages", []))
            token = data.get("nextPageToken")
            if not token:
                break
        return ids

    def get_message(self, message_id: str) -> dict:
        return self._get(f"messages/{message_id}", {"format": "full"})

    def list_history(self, start_history_id: str):
        """Mudanças na INBOX desde `start_history_id`.

        Retorna (registros, historyId_atual). Lança HistoryExpired se o id expirou.
        """
        records, token, latest = [], None, start_history_id
        while True:
            params = {"startHistoryId": start_history_id, "labelId": "INBOX", "maxResults": 500}
            if token:
                params["pageToken"] = token
            try:
                data = self._get("history", params)
            except NotFound as exc:
                raise HistoryExpired("historyId expirado") from exc
            records.extend(data.get("history", []))
            latest = data.get("historyId", latest)
            token = data.get("nextPageToken")
            if not token:
                return records, latest
