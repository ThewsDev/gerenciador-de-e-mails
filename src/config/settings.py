"""Configuração central: nome, caminhos, paleta Dark Mode e escopos Google."""
import os

APP_NAME = "Gerenciador de E-mails"
APP_VERSION = "1.0.0"
DB_FILENAME = "email_manager.db"

# Limites de armazenamento por mensagem (protegem o tamanho do banco).
MAX_BODY_CHARS = 100_000
MAX_SNIPPET_CHARS = 200
MAX_SEARCH_CHARS = 30_000

# Tamanho da lista exibida na caixa de entrada / pesquisa.
LIST_PAGE_SIZE = 30

_data_dir = None


def ensure_data_dir(user_data_dir: str) -> str:
    """Define o diretório privado do app (Android: user_data_dir) e o cria."""
    global _data_dir
    _data_dir = user_data_dir
    os.makedirs(_data_dir, exist_ok=True)
    return _data_dir


def db_path() -> str:
    if _data_dir is None:
        raise RuntimeError("ensure_data_dir() deve ser chamado antes.")
    return os.path.join(_data_dir, DB_FILENAME)


# Paleta oficial (Dark Mode exclusivo)
COLORS = {
    "background": "#0F1626",
    "surface": "#1A2437",
    "surface_alt": "#222E44",
    "primary": "#2563EB",
    "text": "#F8FAFC",
    "text_secondary": "#8B98AD",
    "border": "#2A3650",
}

# Ícones (fonte Lucide em assets/fonts/lucide.ttf)
ICON_FONT = "assets/fonts/lucide.ttf"
ICONS = {
    "mail": "\ue113", "search": "\ue155", "home": "\ue0f8", "inbox": "\ue0fa",
    "folder-check": "\ue332", "folder": "\ue0dc", "settings": "\ue158",
    "refresh": "\ue149", "back": "\ue072",
}

CATEGORY_COLORS = {
    "Acadêmico": "#3B82F6",   # azul
    "Trabalho": "#8B5CF6",    # roxo
    "Financeiro": "#22C55E",  # verde
    "Compras": "#F97316",     # laranja
    "Marketing": "#EC4899",   # rosa
    "Outros": "#6B7280",      # cinza
}

CATEGORIES = list(CATEGORY_COLORS)  # ordem de exibição
DEFAULT_CATEGORY = "Outros"

# --- Permissões solicitadas ao Google Identity Services ---
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

