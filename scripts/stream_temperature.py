"""Send periodic simulated refrigerator temperatures to BloodWatch."""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from bloodwatch.live_data import delete_simulated_temperature_readings


WARNING_CYCLE = (
    ("Normal", (4.0, 4.1, 3.9, 4.0)),
    ("Warming", (4.0, 4.1, 4.2, 4.3)),
    ("Projected crossing", (4.0, 4.4, 4.9, 5.4)),
    ("Actual breach", (4.0, 4.8, 5.6, 6.3)),
    ("Recovery", (4.0, 4.1, 3.9, 4.0)),
)


def send_reading(
    api_url: str,
    refrigerator_id: str,
    temperature_c: float,
    *,
    timestamp: datetime | None = None,
    source: str = "simulator",
) -> None:
    payload = {
        "refrigerator_id": refrigerator_id,
        "timestamp_utc": (timestamp or datetime.now(timezone.utc)).isoformat(),
        "temperature_c": round(temperature_c, 3),
        "reading_valid": True,
        "source": source,
    }
    request = Request(
        f"{api_url.rstrip('/')}/api/readings",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        response.read()
    print(f"{payload['timestamp_utc']} {refrigerator_id}: {payload['temperature_c']:.3f} °C")


def send_warning_cycle_stage(api_url: str, refrigerator_ids: list[str], stage: str, temperatures: tuple[float, ...]) -> None:
    deleted = delete_simulated_temperature_readings(refrigerator_ids)
    now = datetime.now(timezone.utc)
    offsets = (-90, -60, -30, 0)
    print(f"\nSYNTHETIC WARNING-CYCLE DEMONSTRATION — {stage} (cleared {deleted} prior simulator rows)")
    for index, refrigerator_id in enumerate(refrigerator_ids):
        values = temperatures if index == 0 else (4.0, 4.1, 3.9, 4.0)
        for offset_minutes, temperature in zip(offsets, values):
            send_reading(
                api_url,
                refrigerator_id,
                temperature,
                timestamp=now + timedelta(minutes=offset_minutes),
                source="simulator-warning-cycle",
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="BloodWatch API base URL")
    parser.add_argument("--interval", type=float, default=15, help="Seconds between reading cycles")
    parser.add_argument("--refrigerators", default="R1,R2,R3", help="Comma-separated refrigerator IDs")
    parser.add_argument("--profile", choices=("normal", "warning-cycle"), default="normal", help="Normal feed or fast synthetic warning-cycle demonstration")
    parser.add_argument("--stage-seconds", type=float, default=6, help="Seconds to show each warning-cycle stage")
    parser.add_argument("--once", action="store_true", help="Send one cycle and exit")
    arguments = parser.parse_args()
    refrigerator_ids = [value.strip() for value in arguments.refrigerators.split(",") if value.strip()]
    if arguments.interval <= 0 or arguments.stage_seconds <= 0 or not refrigerator_ids:
        parser.error("interval and stage-seconds must be positive and at least one refrigerator ID is required")

    if arguments.profile == "warning-cycle":
        while True:
            for stage, temperatures in WARNING_CYCLE:
                try:
                    send_warning_cycle_stage(arguments.api_url, refrigerator_ids, stage, temperatures)
                except (HTTPError, URLError, TimeoutError) as error:
                    print(f"Could not send warning-cycle stage {stage}: {error}")
                time.sleep(arguments.stage_seconds)
            if arguments.once:
                return 0

    randomizer = random.Random()
    cycle = 0
    while True:
        for index, refrigerator_id in enumerate(refrigerator_ids):
            phase = cycle / 8 + index * 0.6
            temperature = 4.0 + 0.12 * math.sin(phase) + randomizer.gauss(0, 0.025)
            try:
                send_reading(arguments.api_url, refrigerator_id, temperature)
            except (HTTPError, URLError, TimeoutError) as error:
                print(f"Could not send {refrigerator_id} reading: {error}")
        cycle += 1
        if arguments.once:
            return 0
        time.sleep(arguments.interval)


if __name__ == "__main__":
    raise SystemExit(main())
