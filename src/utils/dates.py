"""Utilitários de data. O banco guarda datas como epoch em milissegundos (UTC),
o mesmo formato do campo `internalDate` da Gmail API."""
import time
from datetime import date, datetime, timedelta


def now_ms() -> int:
    return int(time.time() * 1000)


def local_day_range_ms(day: date):
    """Intervalo [início, fim) em ms do dia civil `day` no fuso do dispositivo."""
    start = datetime(day.year, day.month, day.day)
    end = start + timedelta(days=1)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)
