"""Normalização de texto para busca e classificação (sem acentos, sem caixa)."""
import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")


def normalize_text(value) -> str:
    """Minúsculas, sem acentos e com espaços colapsados.

    'Fatura do Cartão' -> 'fatura do cartao'. Usado ao gravar e ao consultar,
    pois o LIKE do SQLite só ignora caixa para ASCII (não para 'Á' vs 'á').
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _WHITESPACE.sub(" ", stripped.casefold()).strip()


def split_terms(query) -> list:
    """Divide uma consulta em termos normalizados (todos devem casar)."""
    return [term for term in normalize_text(query).split(" ") if term]


def collapse_whitespace(value, limit: int = 0) -> str:
    """Remove quebras/espaços repetidos; opcionalmente trunca em `limit`."""
    text = _WHITESPACE.sub(" ", str(value or "")).strip()
    return text[:limit] if limit else text
