from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Europe/Berlin")


def format_dt(value):
    if not value:
        return ""
    return datetime.fromisoformat(value).astimezone(TIMEZONE).strftime("%d.%m.%Y um %H:%M Uhr")
