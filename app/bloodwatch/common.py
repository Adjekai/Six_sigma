from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value}")
    return parsed.astimezone(timezone.utc)


def warning(code: str, message: str, level: str = "warning") -> dict[str, str]:
    return {"code": code, "level": level, "message": message}


def finite_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    if value == float("inf") or value == float("-inf") or value != value:
        return None
    return value


def require_nonnegative(value: float, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")


JsonDict = dict[str, Any]
