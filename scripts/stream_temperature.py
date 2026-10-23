"""Send periodic simulated refrigerator temperatures to BloodWatch."""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="BloodWatch API base URL")
    parser.add_argument("--interval", type=float, default=15, help="Seconds between reading cycles")
    parser.add_argument("--refrigerators", default="R1,R2,R3", help="Comma-separated refrigerator IDs")
    parser.add_argument("--once", action="store_true", help="Send one cycle and exit")
    arguments = parser.parse_args()
    refrigerator_ids = [value.strip() for value in arguments.refrigerators.split(",") if value.strip()]
    if arguments.interval <= 0 or not refrigerator_ids:
        parser.error("interval must be positive and at least one refrigerator ID is required")

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
