import os
from datetime import datetime
from zoneinfo import ZoneInfo

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "America/Argentina/Buenos_Aires")


def now_local() -> datetime:
    """Fecha/hora local sin tzinfo para guardar de forma consistente en SQLite."""
    return datetime.now(ZoneInfo(APP_TIMEZONE)).replace(tzinfo=None)
