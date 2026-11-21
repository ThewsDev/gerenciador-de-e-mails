"""Converte linhas do banco em dicionários prontos para a interface (sem dependência do Kivy)."""
from datetime import datetime
from typing import Optional

_WEEKDAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def format_list_date(ms: int, now: Optional[datetime] = None) -> str:
    """'09:42' (hoje), 'Ontem', 'Segunda' (últimos 6 dias) ou '12/10/2026'."""
    now = now or datetime.now()
    moment = datetime.fromtimestamp(ms / 1000)
    days = (now.date() - moment.date()).days
    if days == 0:
        return f"{moment:%H:%M}"
    if days == 1:
        return "Ontem"
    if 1 < days < 7:
        return _WEEKDAYS[moment.weekday()]
    return f"{moment:%d/%m/%Y}"


def format_full_date(ms: int) -> str:
    return f"{datetime.fromtimestamp(ms / 1000):%d/%m/%Y · %H:%M}"


def format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.0f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def to_view_model(row: dict, now: Optional[datetime] = None) -> dict:
    """Dicionário no formato esperado pelos componentes de UI."""
    view = dict(row)
    view["sender"] = row.get("sender_name") or row.get("sender_email") or "(Remetente desconhecido)"
    view["subject"] = row.get("subject") or "(Sem assunto)"
    view["preview"] = row.get("snippet", "")
    view["date"] = format_list_date(row["internal_date"], now)
    view["date_full"] = format_full_date(row["internal_date"])
    return view
