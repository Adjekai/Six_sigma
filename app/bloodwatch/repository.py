from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .common import parse_utc


ROOT = Path(__file__).resolve().parents[2]
SCENARIO_ROOT = ROOT / "data" / "scenarios"


class ScenarioDataError(ValueError):
    pass


def _read_csv(folder: Path, name: str) -> list[dict[str, str]]:
    path = folder / name
    if not path.exists():
        raise ScenarioDataError(f"Missing scenario table: {name}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def available_scenarios() -> list[dict[str, Any]]:
    scenarios = []
    if not SCENARIO_ROOT.exists():
        return scenarios
    for folder in sorted(path for path in SCENARIO_ROOT.iterdir() if path.is_dir()):
        metadata_path = folder / "metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            scenarios.append(
                {
                    "id": metadata["id"],
                    "name": metadata["name"],
                    "description": metadata["description"],
                    "synthetic": bool(metadata.get("synthetic", False)),
                }
            )
    return scenarios


def load_scenario(scenario_id: str) -> dict[str, Any]:
    if not scenario_id or any(character not in "abcdefghijklmnopqrstuvwxyz_" for character in scenario_id):
        raise ScenarioDataError("Invalid scenario ID")
    folder = SCENARIO_ROOT / scenario_id
    if not folder.is_dir():
        raise FileNotFoundError(f"Unknown scenario: {scenario_id}")

    metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    data = {
        "metadata": metadata,
        "equipment": _read_csv(folder, "equipment_exposure.csv"),
        "temperatures": _read_csv(folder, "temperatures.csv"),
        "incidents": _read_csv(folder, "cooling_incidents.csv"),
        "blackouts": _read_csv(folder, "blackout_demands.csv"),
        "inventory": _read_csv(folder, "inventory_outcomes.csv"),
    }
    _coerce(data)
    _validate(data)
    return data


def _blank_to_none(value: str) -> str | None:
    return None if value == "" else value


def _coerce(data: dict[str, Any]) -> None:
    data["metadata"]["reference_time"] = parse_utc(data["metadata"]["reference_time_utc"])
    for row in data["equipment"]:
        row["observation_start"] = parse_utc(row.pop("observation_start_utc"))
        row["observation_end"] = parse_utc(row.pop("observation_end_utc"))
        row["mechanical_operating_hours"] = float(row["mechanical_operating_hours"])
    for row in data["temperatures"]:
        row["timestamp"] = parse_utc(row.pop("timestamp_utc"))
        row["temperature_c"] = None if row["temperature_c"] == "" else float(row["temperature_c"])
        row["reading_valid"] = row["reading_valid"].lower() == "true"
    for row in data["incidents"]:
        row["cooling_loss"] = parse_utc(row.pop("cooling_loss_utc"))
        row["observation_end"] = parse_utc(row.pop("observation_end_utc"))
        restored = _blank_to_none(row.pop("cooling_restored_utc"))
        row["cooling_restored"] = parse_utc(restored) if restored else None
        row["blackout_id"] = _blank_to_none(row["blackout_id"])
    for row in data["blackouts"]:
        row["start"] = parse_utc(row.pop("start_utc"))
        row["end"] = parse_utc(row.pop("end_utc"))
    for row in data["inventory"]:
        row["as_of"] = parse_utc(row.pop("as_of_utc"))
        row["incident_id"] = _blank_to_none(row["incident_id"])
        for field in ("bags_present", "bags_transferred", "bags_written_off"):
            row[field] = None if row[field] == "" else int(row[field])
        row["value_per_bag_usd"] = None if row["value_per_bag_usd"] == "" else float(row["value_per_bag_usd"])


def _duplicates(values: list[str]) -> set[str]:
    return {value for value in values if values.count(value) > 1}


def _validate(data: dict[str, Any]) -> None:
    equipment_ids = [row["equipment_id"] for row in data["equipment"]]
    if duplicates := _duplicates(equipment_ids):
        raise ScenarioDataError(f"Repeated equipment IDs: {sorted(duplicates)}")
    equipment_set = set(equipment_ids)

    incident_ids = [row["incident_id"] for row in data["incidents"]]
    if duplicates := _duplicates(incident_ids):
        raise ScenarioDataError(f"Repeated incident IDs: {sorted(duplicates)}")
    blackout_ids = [row["blackout_id"] for row in data["blackouts"]]
    if duplicates := _duplicates(blackout_ids):
        raise ScenarioDataError(f"Repeated blackout IDs: {sorted(duplicates)}")

    for row in data["equipment"]:
        if row["mechanical_operating_hours"] < 0:
            raise ScenarioDataError("Mechanical operating hours cannot be negative")
        if row["observation_start"] >= row["observation_end"]:
            raise ScenarioDataError(f"Invalid observation dates for {row['equipment_id']}")
    for row in data["temperatures"]:
        if row["refrigerator_id"] not in equipment_set:
            raise ScenarioDataError(f"Unknown refrigerator in temperatures: {row['refrigerator_id']}")
    for row in data["incidents"]:
        if row["refrigerator_id"] not in equipment_set:
            raise ScenarioDataError(f"Unknown refrigerator in incident: {row['refrigerator_id']}")
        if row["observation_end"] < row["cooling_loss"]:
            raise ScenarioDataError(f"Incident ends before cooling loss: {row['incident_id']}")
        if row["cooling_restored"] and row["cooling_restored"] < row["cooling_loss"]:
            raise ScenarioDataError(f"Recovery precedes cooling loss: {row['incident_id']}")
        if row["cause"].startswith("blackout") and not row["blackout_id"]:
            raise ScenarioDataError(f"Blackout incident lacks blackout ID: {row['incident_id']}")
    for equipment_id in equipment_ids:
        intervals = sorted(
            (row["cooling_loss"], row["observation_end"], row["incident_id"])
            for row in data["incidents"]
            if row["refrigerator_id"] == equipment_id
        )
        for previous, current in zip(intervals, intervals[1:]):
            if current[0] < previous[1]:
                raise ScenarioDataError(f"Overlapping incidents: {previous[2]} and {current[2]}")
    for row in data["blackouts"]:
        if row["end"] < row["start"]:
            raise ScenarioDataError(f"Blackout ends before it starts: {row['blackout_id']}")
        if row["auto_start_outcome"] not in {"success", "failure", "unknown"}:
            raise ScenarioDataError(f"Invalid generator outcome: {row['blackout_id']}")
    for row in data["inventory"]:
        counts = (row["bags_present"], row["bags_transferred"], row["bags_written_off"])
        if any(value is not None and value < 0 for value in counts):
            raise ScenarioDataError("Inventory counts cannot be negative")
        if row["value_per_bag_usd"] is not None and row["value_per_bag_usd"] < 0:
            raise ScenarioDataError("Inventory value cannot be negative")
        transferred = row["bags_transferred"] or 0
        written_off = row["bags_written_off"] or 0
        if transferred + written_off > row["bags_present"]:
            raise ScenarioDataError(f"Outcomes exceed eligible bags for lot {row['lot_id']}")
