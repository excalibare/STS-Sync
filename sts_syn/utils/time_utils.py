from __future__ import annotations

from datetime import datetime, timezone


def timestamp_for_path() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def format_dt(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")
