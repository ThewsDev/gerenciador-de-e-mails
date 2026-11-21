"""Mantém o access token somente em memória durante a sessão do app.

O Google Identity Services mantém seu próprio cache protegido de autorização no
Android. O app não persiste access tokens nem refresh tokens em SQLite/arquivos.
"""


class TokenStore:
    def __init__(self):
        self._access_token = None

    def set_access_token(self, token: str) -> None:
        if not token or not isinstance(token, str):
            raise ValueError("Access token inválido.")
        self._access_token = token

    def get_access_token(self):
        return self._access_token

    def clear(self) -> None:
        self._access_token = None

    def has_token(self) -> bool:
        return bool(self._access_token)
