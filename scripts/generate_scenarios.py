"""Generate BloodWatch's reproducible, related synthetic datasets."""

from __future__ import annotations

import csv
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data"
REFERENCE = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
BASELINE_START = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
BASELINE_END = datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc)
REFRIGERATORS = ("R1", "R2", "R3")


def iso(value: datetime | None) -> str:
    return "" if value is None else value.isoformat().replace("+00:00", "Z")


def write_csv(name: str, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"{name} must contain at least one row")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def refrigerator_rows() -> list[dict[str, object]]:
    historical_start = datetime(2021, 10, 20, 12, 0, tzinfo=timezone.utc)
    recent_start = BASELINE_END
    rows: list[dict[str, object]] = []
    histories = {
        "R1": (15_000.0, 286.0, None),
        "R2": (16_000.0, 288.0, "RF-001"),
        "R3": (17_000.0, 288.0, None),
    }
    inventories = {"R1": (400, 2), "R2": (350, 2), "R3": (300, 2)}
    for refrigerator_id in REFRIGERATORS:
        historical_hours, recent_hours, historical_event = histories[refrigerator_id]
        rows.extend(
            [
                {
                    "operating_period_id": f"OP-{refrigerator_id}-HIST",
                    "refrigerator_id": refrigerator_id,
                    "site_id": "BLOOD-BANK-1",
                    "model_group": "CW-100",
                    "generator_id": "G1",
                    "period_start_utc": iso(historical_start),
                    "period_end_utc": iso(BASELINE_START),
                    "observed_operating_hours": f"{historical_hours:.1f}",
                    "mechanical_failure": "true" if historical_event else "false",
                    "failure_event_id": historical_event or "",
                    "cooling_loss_utc": iso(datetime(2025, 4, 12, 9, 0, tzinfo=timezone.utc)) if historical_event else "",
                    "cooling_restored_utc": iso(datetime(2025, 4, 12, 10, 30, tzinfo=timezone.utc)) if historical_event else "",
                    "normal_baseline": "false",
                    "current_bags": "",
                    "current_lot_count": "",
                    "value_per_bag_usd": "",
                },
                {
                    "operating_period_id": f"OP-{refrigerator_id}-BASE",
                    "refrigerator_id": refrigerator_id,
                    "site_id": "BLOOD-BANK-1",
                    "model_group": "CW-100",
                    "generator_id": "G1",
                    "period_start_utc": iso(BASELINE_START),
                    "period_end_utc": iso(BASELINE_END),
                    "observed_operating_hours": "168.0",
                    "mechanical_failure": "false",
                    "failure_event_id": "",
                    "cooling_loss_utc": "",
                    "cooling_restored_utc": "",
                    "normal_baseline": "true",
                    "current_bags": "",
                    "current_lot_count": "",
                    "value_per_bag_usd": "",
                },
                {
                    "operating_period_id": f"OP-{refrigerator_id}-CURRENT",
                    "refrigerator_id": refrigerator_id,
                    "site_id": "BLOOD-BANK-1",
                    "model_group": "CW-100",
                    "generator_id": "G1",
                    "period_start_utc": iso(recent_start),
                    "period_end_utc": iso(REFERENCE),
                    "observed_operating_hours": f"{recent_hours:.1f}",
                    "mechanical_failure": "true" if refrigerator_id == "R1" else "false",
                    "failure_event_id": "RF-002" if refrigerator_id == "R1" else "",
                    "cooling_loss_utc": iso(datetime(2026, 10, 19, 16, 0, tzinfo=timezone.utc)) if refrigerator_id == "R1" else "",
                    "cooling_restored_utc": iso(datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc)) if refrigerator_id == "R1" else "",
                    "normal_baseline": "false",
                    "current_bags": inventories[refrigerator_id][0],
                    "current_lot_count": inventories[refrigerator_id][1],
                    "value_per_bag_usd": "240.00",
                },
            ]
        )
    return rows


def generator_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    origin = datetime(2022, 1, 15, 8, 0, tzinfo=timezone.utc)
    for index in range(1, 20):
        start = origin + timedelta(days=80 * (index - 1))
        failed = index == 5
        rows.append(
            {
                "blackout_event_id": f"GF-{index:03d}",
                "generator_id": "G1",
                "site_id": "BLOOD-BANK-1",
                "blackout_start_utc": iso(start),
                "blackout_end_utc": iso(start + timedelta(hours=2)),
                "start_outcome": "failure" if failed else "success",
                "cooling_loss_utc": iso(start) if failed else "",
                "cooling_restored_utc": iso(start + timedelta(hours=1, minutes=45)) if failed else "",
            }
        )
    current_start = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)
    rows.append(
        {
            "blackout_event_id": "GF-020",
            "generator_id": "G1",
            "site_id": "BLOOD-BANK-1",
            "blackout_start_utc": iso(current_start),
            "blackout_end_utc": iso(current_start + timedelta(hours=2, minutes=30)),
            "start_outcome": "failure",
            "cooling_loss_utc": iso(current_start),
            "cooling_restored_utc": iso(current_start + timedelta(hours=2)),
        }
    )
    unknown_start = datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc)
    rows.append(
        {
            "blackout_event_id": "GF-021",
            "generator_id": "G1",
            "site_id": "BLOOD-BANK-1",
            "blackout_start_utc": iso(unknown_start),
            "blackout_end_utc": iso(unknown_start + timedelta(minutes=40)),
            "start_outcome": "unknown",
            "cooling_loss_utc": "",
            "cooling_restored_utc": "",
        }
    )
    return sorted(rows, key=lambda row: row["blackout_start_utc"])


def normal_temperature(rng: random.Random, refrigerator_id: str, timestamp: datetime) -> float:
    phase = {"R1": 0.0, "R2": 0.7, "R3": 1.4}[refrigerator_id]
    cycle = 0.10 * math.sin(timestamp.timestamp() / 3_600 + phase)
    return 4.0 + cycle + rng.gauss(0, 0.07)


def temperature_rows() -> list[dict[str, object]]:
    rng = random.Random(5930)
    rows: list[dict[str, object]] = []
    ranges = (
        (BASELINE_START, BASELINE_END),
        (REFERENCE - timedelta(hours=24), REFERENCE + timedelta(minutes=1)),
    )
    mechanical = {
        datetime(2026, 10, 19, 16, 0, tzinfo=timezone.utc) + timedelta(minutes=15 * i): value
        for i, value in enumerate((4.0, 4.4, 4.9, 5.5, 6.0, 6.4, 6.8, 5.6, 4.7))
    }
    blackout_profiles = {
        refrigerator_id: {
            datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc) + timedelta(minutes=15 * i): value
            for i, value in enumerate(values)
        }
        for refrigerator_id, values in {
            "R1": (4.0, 4.5, 5.0, 5.6, 6.0, 6.5, 7.1, 5.8, 4.8),
            "R2": (4.0, 4.4, 4.9, 5.4, 5.9, 6.3, 6.1, 5.2, 4.5),
            "R3": (4.0, 4.3, 4.7, 5.1, 5.4, 5.7, 5.5, 4.9, 4.4),
        }.items()
    }
    for refrigerator_id in REFRIGERATORS:
        for start, end in ranges:
            timestamp = start
            while timestamp < end:
                value = normal_temperature(rng, refrigerator_id, timestamp)
                event_id = ""
                if refrigerator_id == "R1" and timestamp in mechanical:
                    value, event_id = mechanical[timestamp], "RF-002"
                if timestamp in blackout_profiles[refrigerator_id]:
                    value, event_id = blackout_profiles[refrigerator_id][timestamp], "GF-020"
                valid = not (refrigerator_id == "R3" and timestamp == REFERENCE - timedelta(hours=18))
                rows.append(
                    {
                        "timestamp_utc": iso(timestamp),
                        "refrigerator_id": refrigerator_id,
                        "temperature_c": f"{value:.2f}" if valid else "",
                        "reading_valid": "true" if valid else "false",
                        "related_failure_event_id": event_id,
                    }
                )
                timestamp += timedelta(minutes=15)

    historical_generator_start = datetime(2022, 1, 15, 8, 0, tzinfo=timezone.utc) + timedelta(days=80 * 4)
    historical_profiles = {
        ("R1", "GF-005", historical_generator_start): (4.0, 4.5, 5.0, 5.6, 6.2, 6.4, 5.4, 4.3),
        ("R2", "GF-005", historical_generator_start): (4.0, 4.4, 4.8, 5.2, 5.5, 5.8, 5.1, 4.2),
        ("R3", "GF-005", historical_generator_start): (4.0, 4.3, 4.7, 5.0, 5.3, 5.6, 5.0, 4.2),
        ("R2", "RF-001", datetime(2025, 4, 12, 9, 0, tzinfo=timezone.utc)): (4.0, 4.5, 5.1, 5.8, 6.2, 5.4, 4.4),
    }
    for (refrigerator_id, event_id, start), values in historical_profiles.items():
        for index, value in enumerate(values):
            rows.append(
                {
                    "timestamp_utc": iso(start + timedelta(minutes=15 * index)),
                    "refrigerator_id": refrigerator_id,
                    "temperature_c": f"{value:.2f}",
                    "reading_valid": "true",
                    "related_failure_event_id": event_id,
                }
            )
    return sorted(rows, key=lambda row: (row["timestamp_utc"], row["refrigerator_id"]))


def main() -> None:
    write_csv("blood_temperature.csv", temperature_rows())
    write_csv("refrigerator_failures.csv", refrigerator_rows())
    write_csv("generator_failures.csv", generator_rows())
    print(f"Generated 3 related datasets in {OUTPUT}")


if __name__ == "__main__":
    main()
