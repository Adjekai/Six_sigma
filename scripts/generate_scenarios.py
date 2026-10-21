"""Generate the three reproducible BloodWatch demonstration scenarios."""

from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "scenarios"
REFERENCE = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def iso(value: datetime | None) -> str:
    return "" if value is None else value.isoformat().replace("+00:00", "Z")


def write_csv(folder: Path, name: str, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"{name} must contain at least one row")
    with (folder / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def temperature_rows(
    rng: random.Random,
    refrigerator_ids: list[str],
    event_profiles: dict[str, dict[int, float]] | None = None,
) -> list[dict]:
    """Create 15-minute readings for the 24-hour display window."""
    rows: list[dict] = []
    event_profiles = event_profiles or {}
    start = REFERENCE - timedelta(hours=24)
    for refrigerator_id in refrigerator_ids:
        profile = event_profiles.get(refrigerator_id, {})
        for index in range(97):
            timestamp = start + timedelta(minutes=15 * index)
            base = 4.0 + rng.gauss(0, 0.12)
            value = profile.get(index, base)
            rows.append(
                {
                    "timestamp_utc": iso(timestamp),
                    "refrigerator_id": refrigerator_id,
                    "temperature_c": f"{value:.2f}",
                    "reading_valid": "true",
                }
            )
    return rows


def equipment_rows(ids: list[str], site: str, generator: str, hours: list[float]) -> list[dict]:
    start = REFERENCE - timedelta(days=365 * 5)
    return [
        {
            "equipment_id": equipment_id,
            "site_id": site,
            "equipment_type": "refrigerator",
            "model_group": "CW-100",
            "generator_id": generator,
            "observation_start_utc": iso(start),
            "observation_end_utc": iso(REFERENCE),
            "mechanical_operating_hours": f"{operating_hours:.1f}",
        }
        for equipment_id, operating_hours in zip(ids, hours, strict=True)
    ]


def historical_blackouts(site: str, generator: str, count: int, failed_indexes: set[int]) -> list[dict]:
    rows = []
    start = REFERENCE - timedelta(days=365 * 5)
    for index in range(count):
        event_start = start + timedelta(days=80 * index, hours=8)
        rows.append(
            {
                "blackout_id": f"BLK-{site}-{index + 1:02d}",
                "site_id": site,
                "generator_id": generator,
                "start_utc": iso(event_start),
                "end_utc": iso(event_start + timedelta(hours=2)),
                "auto_start_outcome": "failure" if index in failed_indexes else "success",
            }
        )
    return rows


def current_snapshots(refrigerator_ids: list[str], values: list[tuple[int, float]]) -> list[dict]:
    return [
        {
            "record_type": "current_snapshot",
            "as_of_utc": iso(REFERENCE),
            "incident_id": "",
            "lot_id": f"LOT-{refrigerator_id}",
            "refrigerator_id": refrigerator_id,
            "bags_present": bags,
            "value_per_bag_usd": f"{value:.2f}",
            "bags_transferred": "",
            "bags_written_off": "",
        }
        for refrigerator_id, (bags, value) in zip(refrigerator_ids, values, strict=True)
    ]


def build_normal() -> dict:
    rng = random.Random(1101)
    refrigerator_ids = ["R-N1", "R-N2"]
    blackout_rows = historical_blackouts("NORTH", "G-N", 10, set())
    recent_blackout = blackout_rows[-1]
    cooling_loss = datetime.fromisoformat(recent_blackout["start_utc"].replace("Z", "+00:00"))
    incidents = [
        {
            "incident_id": "INC-N-BLACKOUT",
            "refrigerator_id": "R-N1",
            "cause": "blackout_interruption",
            "cooling_loss_utc": iso(cooling_loss),
            "observation_end_utc": iso(cooling_loss + timedelta(minutes=30)),
            "cooling_restored_utc": iso(cooling_loss + timedelta(minutes=10)),
            "blackout_id": recent_blackout["blackout_id"],
        },
        {
            "incident_id": "INC-N-MECH-OLD",
            "refrigerator_id": "R-N2",
            "cause": "mechanical",
            "cooling_loss_utc": iso(REFERENCE - timedelta(days=120, hours=3)),
            "observation_end_utc": iso(REFERENCE - timedelta(days=120)),
            "cooling_restored_utc": iso(REFERENCE - timedelta(days=120, hours=1)),
            "blackout_id": "",
        },
    ]
    inventory = current_snapshots(refrigerator_ids, [(40, 240), (35, 240)])
    inventory.append(
        {
            "record_type": "incident_outcome",
            "as_of_utc": iso(REFERENCE - timedelta(days=120)),
            "incident_id": "INC-N-MECH-OLD",
            "lot_id": "LOT-N-OLD",
            "refrigerator_id": "R-N2",
            "bags_present": 20,
            "value_per_bag_usd": "240.00",
            "bags_transferred": 20,
            "bags_written_off": 0,
        }
    )
    return {
        "id": "normal",
        "name": "Normal / resilient",
        "description": "Temperatures remain within limits and all recorded backup starts succeed.",
        "seed": 1101,
        "equipment": equipment_rows(refrigerator_ids, "NORTH", "G-N", [15000, 18000]),
        "temperatures": temperature_rows(rng, refrigerator_ids),
        "incidents": incidents,
        "blackouts": blackout_rows,
        "inventory": inventory,
        "planted_truth": ["No current breach", "No failed generator starts", "One historical zero-loss mechanical incident"],
    }


def build_breakdown() -> dict:
    rng = random.Random(2202)
    refrigerator_ids = ["R-B1", "R-B2"]
    # Index 80 is 08:00 on the displayed reference day.
    warming = {80 + offset: value for offset, value in enumerate([4.0, 4.4, 4.9, 5.5, 6.0, 6.4, 6.8, 5.7, 4.8])}
    incidents = [
        {
            "incident_id": "INC-B-MECH-1",
            "refrigerator_id": "R-B1",
            "cause": "mechanical",
            "cooling_loss_utc": iso(REFERENCE - timedelta(hours=4)),
            "observation_end_utc": iso(REFERENCE - timedelta(hours=1, minutes=45)),
            "cooling_restored_utc": iso(REFERENCE - timedelta(hours=2)),
            "blackout_id": "",
        },
        {
            "incident_id": "INC-B-MECH-2",
            "refrigerator_id": "R-B2",
            "cause": "mechanical",
            "cooling_loss_utc": iso(REFERENCE - timedelta(days=40, hours=2)),
            "observation_end_utc": iso(REFERENCE - timedelta(days=40)),
            "cooling_restored_utc": iso(REFERENCE - timedelta(days=40, hours=1)),
            "blackout_id": "",
        },
    ]
    inventory = current_snapshots(refrigerator_ids, [(50, 250), (32, 250)])
    inventory.extend(
        [
            {
                "record_type": "incident_outcome",
                "as_of_utc": iso(REFERENCE - timedelta(hours=1)),
                "incident_id": "INC-B-MECH-1",
                "lot_id": "LOT-B-LOSS",
                "refrigerator_id": "R-B1",
                "bags_present": 50,
                "value_per_bag_usd": "250.00",
                "bags_transferred": 20,
                "bags_written_off": 30,
            },
            {
                "record_type": "incident_outcome",
                "as_of_utc": iso(REFERENCE - timedelta(days=40)),
                "incident_id": "INC-B-MECH-2",
                "lot_id": "LOT-B-ZERO",
                "refrigerator_id": "R-B2",
                "bags_present": 25,
                "value_per_bag_usd": "250.00",
                "bags_transferred": 25,
                "bags_written_off": 0,
            },
        ]
    )
    return {
        "id": "refrigerator_breakdown",
        "name": "Refrigerator breakdown",
        "description": "A mechanical failure causes warming, a detected limit breach, recovery, and simulated write-off.",
        "seed": 2202,
        "equipment": equipment_rows(refrigerator_ids, "CENTRAL", "G-C", [10000, 10000]),
        "temperatures": temperature_rows(rng, refrigerator_ids, {"R-B1": warming}),
        "incidents": incidents,
        "blackouts": historical_blackouts("CENTRAL", "G-C", 8, set()),
        "inventory": inventory,
        "planted_truth": ["2 mechanical failures / 20,000 operating hours", "R-B1 breaches above 6 C", "$7,500 simulated historical write-off"],
    }


def build_blackout() -> dict:
    rng = random.Random(3303)
    refrigerator_ids = ["R-O1", "R-O2", "R-O3"]
    blackout_rows = historical_blackouts("WEST", "G-W", 19, {4})
    current_start = REFERENCE - timedelta(hours=3)
    blackout_rows.append(
        {
            "blackout_id": "BLK-WEST-20",
            "site_id": "WEST",
            "generator_id": "G-W",
            "start_utc": iso(current_start),
            "end_utc": iso(REFERENCE - timedelta(minutes=30)),
            "auto_start_outcome": "failure",
        }
    )
    profiles: dict[str, dict[int, float]] = {}
    for refrigerator_id, peak in zip(refrigerator_ids, [7.1, 6.3, 5.7], strict=True):
        values = [4.0, 4.5, 5.0, 5.6, min(6.0, peak), peak, max(4.8, peak - 0.8), 4.5]
        profiles[refrigerator_id] = {84 + offset: value for offset, value in enumerate(values)}
    incidents = [
        {
            "incident_id": f"INC-O-{index + 1}",
            "refrigerator_id": refrigerator_id,
            "cause": "blackout_failed_start",
            "cooling_loss_utc": iso(current_start),
            "observation_end_utc": iso(REFERENCE),
            "cooling_restored_utc": iso(REFERENCE - timedelta(hours=1)),
            "blackout_id": "BLK-WEST-20",
        }
        for index, refrigerator_id in enumerate(refrigerator_ids)
    ]
    inventory = current_snapshots(refrigerator_ids, [(40, 250), (36, 250), (24, 250)])
    inventory.extend(
        [
            {
                "record_type": "incident_outcome",
                "as_of_utc": iso(REFERENCE),
                "incident_id": "INC-O-1",
                "lot_id": "LOT-O-SHARED",
                "refrigerator_id": "R-O1",
                "bags_present": 40,
                "value_per_bag_usd": "250.00",
                "bags_transferred": 20,
                "bags_written_off": 20,
            },
            {
                "record_type": "incident_outcome",
                "as_of_utc": iso(REFERENCE),
                "incident_id": "INC-O-2",
                "lot_id": "LOT-O-2",
                "refrigerator_id": "R-O2",
                "bags_present": 36,
                "value_per_bag_usd": "250.00",
                "bags_transferred": 36,
                "bags_written_off": 0,
            },
            {
                "record_type": "incident_outcome",
                "as_of_utc": iso(REFERENCE),
                "incident_id": "INC-O-3",
                "lot_id": "LOT-O-3",
                "refrigerator_id": "R-O3",
                "bags_present": 24,
                "value_per_bag_usd": "250.00",
                "bags_transferred": 24,
                "bags_written_off": 0,
            },
        ]
    )
    return {
        "id": "blackout_failed_backup",
        "name": "Blackout / failed backup",
        "description": "One blackout demand affects three refrigerators and the automatic generator start fails.",
        "seed": 3303,
        "equipment": equipment_rows(refrigerator_ids, "WEST", "G-W", [16000, 17000, 17500]),
        "temperatures": temperature_rows(rng, refrigerator_ids, profiles),
        "incidents": incidents,
        "blackouts": blackout_rows,
        "inventory": inventory,
        "planted_truth": ["One blackout and one generator demand", "2 failures / 20 known demands", "Two refrigerators breach; one remains within limits"],
    }


def generate() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for scenario in (build_normal(), build_breakdown(), build_blackout()):
        folder = OUTPUT / scenario["id"]
        folder.mkdir(parents=True, exist_ok=True)
        write_csv(folder, "equipment_exposure.csv", scenario["equipment"])
        write_csv(folder, "temperatures.csv", scenario["temperatures"])
        write_csv(folder, "cooling_incidents.csv", scenario["incidents"])
        write_csv(folder, "blackout_demands.csv", scenario["blackouts"])
        write_csv(folder, "inventory_outcomes.csv", scenario["inventory"])
        metadata = {
            "id": scenario["id"],
            "name": scenario["name"],
            "description": scenario["description"],
            "synthetic": True,
            "reference_time_utc": iso(REFERENCE),
            "seed": scenario["seed"],
            "generation_assumptions": [
                "Illustrative warming profiles are not validated biological or thermal models.",
                "Failure histories use constant rates within each modeled group.",
                "All values, events, inventory, and outcomes are synthetic.",
            ],
            "planted_truth": scenario["planted_truth"],
        }
        (folder / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    generate()
    print(f"Generated BloodWatch scenarios in {OUTPUT}")
