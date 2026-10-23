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
) -> bool:
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
        timestamp_text = timestamp.astimezone(timezone.utc).isoformat()
        if connection.execute(
            "SELECT 1 FROM temperature_readings WHERE refrigerator_id = ? AND timestamp_utc = ? LIMIT 1",
            (refrigerator_id, timestamp_text),
        ).fetchone():
            return False
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO temperature_readings
                (refrigerator_id, timestamp_utc, temperature_c, reading_valid, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            (refrigerator_id, timestamp_text, temperature_c, int(reading_valid), source),
        )
        return cursor.rowcount == 1


def record_rejected_reading(reason: str) -> None:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=10) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS rejected_readings (reason TEXT NOT NULL, rejected_at_utc TEXT NOT NULL)")
        connection.execute("INSERT INTO rejected_readings VALUES (?, ?)", (reason, datetime.now(timezone.utc).isoformat()))


def rejected_reading_summary() -> dict[str, Any]:
    path = _database_path()
    if not path.exists():
        return {"count": 0, "reasons": []}
    with sqlite3.connect(path, timeout=10) as connection:
        try:
            rows = connection.execute("SELECT reason, COUNT(*) FROM rejected_readings GROUP BY reason ORDER BY reason").fetchall()
        except sqlite3.OperationalError:
            rows = []
    return {"count": sum(row[1] for row in rows), "reasons": [{"reason": row[0], "count": row[1]} for row in rows]}


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
