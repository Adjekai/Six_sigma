from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import parse_utc


ROOT = Path(__file__).resolve().parents[2]


def _database_path() -> Path:
    return Path(os.environ.get("BLOODWATCH_LIVE_DB", ROOT / "data" / "live_readings.sqlite3"))


def record_temperature_reading(
    refrigerator_id: str,
    timestamp: datetime,
    temperature_c: float | None,
    reading_valid: bool,
    source: str,
) -> None:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS temperature_readings (
                refrigerator_id TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                temperature_c REAL,
                reading_valid INTEGER NOT NULL,
                source TEXT NOT NULL,
                PRIMARY KEY (refrigerator_id, timestamp_utc, source)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO temperature_readings
                (refrigerator_id, timestamp_utc, temperature_c, reading_valid, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (refrigerator_id, timestamp_utc, source) DO UPDATE SET
                temperature_c = excluded.temperature_c,
                reading_valid = excluded.reading_valid
            """,
            (refrigerator_id, timestamp.astimezone(timezone.utc).isoformat(), temperature_c, int(reading_valid), source),
        )


def load_temperature_readings() -> list[dict[str, Any]]:
    path = _database_path()
    if not path.exists():
        return []
    with sqlite3.connect(path, timeout=10) as connection:
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT refrigerator_id, timestamp_utc, temperature_c, reading_valid
                FROM temperature_readings
                ORDER BY timestamp_utc
                """
            ).fetchall()
        except sqlite3.OperationalError as error:
            if "no such table" in str(error):
                return []
            raise
    return [
        {
            "timestamp": parse_utc(row["timestamp_utc"]),
            "refrigerator_id": row["refrigerator_id"],
            "temperature_c": row["temperature_c"],
            "reading_valid": bool(row["reading_valid"]),
            "related_failure_event_id": None,
        }
        for row in rows
    ]