from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .common import parse_utc
from .live_data import load_temperature_readings


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "data"


class DatasetError(ValueError):
    pass


def _read_csv(name: str) -> list[dict[str, str]]:
    path = DATA_ROOT / name
    if not path.exists():
        raise DatasetError(f"Missing dataset: {name}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def known_refrigerator_ids() -> set[str]:
    return {row["refrigerator_id"] for row in _read_csv("refrigerator_failures.csv")}


def _optional_time(value: str) -> Any:
    return parse_utc(value) if value else None


def _optional_int(value: str) -> int | None:
    return int(value) if value else None


def _optional_float(value: str) -> float | None:
    return float(value) if value else None


def _boolean(value: str, field: str) -> bool:
    if value.lower() not in {"true", "false"}:
        raise DatasetError(f"{field} must be true or false")
    return value.lower() == "true"


def load_data(include_live_readings: bool = True) -> dict[str, Any]:
    data = {
        "temperatures": _read_csv("blood_temperature.csv"),
        "refrigerator_periods": _read_csv("refrigerator_failures.csv"),
        "generator_demands": _read_csv("generator_failures.csv"),
    }
    _coerce(data)
    _validate(data)
    baseline_temperatures = [dict(row) for row in data["temperatures"]]
    live_readings = load_temperature_readings() if include_live_readings else []
    live_readings = [row for row in live_readings if row["reading_valid"] and row["temperature_c"] is not None]
    data["live_reading_count"] = len(live_readings)
    data["baseline_temperatures"] = baseline_temperatures
    data["temperatures"].extend(live_readings)
    operational = [
        row["timestamp"] for row in data["temperatures"]
        if row["reading_valid"] and row["temperature_c"] is not None and not _is_baseline_reading(row, data)
    ]
    data["reference_time"] = max(operational)
    return data


def _coerce(data: dict[str, Any]) -> None:
    for row in data["temperatures"]:
        row["timestamp"] = parse_utc(row.pop("timestamp_utc"))
        row["temperature_c"] = _optional_float(row["temperature_c"])
        row["reading_valid"] = _boolean(row["reading_valid"], "reading_valid")
        row["related_failure_event_id"] = row["related_failure_event_id"] or None
    for row in data["refrigerator_periods"]:
        row["period_start"] = parse_utc(row.pop("period_start_utc"))
        row["period_end"] = parse_utc(row.pop("period_end_utc"))
        row["observed_operating_hours"] = float(row["observed_operating_hours"])
        row["mechanical_failure"] = _boolean(row["mechanical_failure"], "mechanical_failure")
        row["failure_event_id"] = row["failure_event_id"] or None
        row["cooling_loss"] = _optional_time(row.pop("cooling_loss_utc"))
        row["cooling_restored"] = _optional_time(row.pop("cooling_restored_utc"))
        row["normal_baseline"] = _boolean(row["normal_baseline"], "normal_baseline")
        row["current_bags"] = _optional_int(row["current_bags"])
        row["current_lot_count"] = _optional_int(row["current_lot_count"])
        row["value_per_bag_usd"] = _optional_float(row["value_per_bag_usd"])
    for row in data["generator_demands"]:
        row["blackout_start"] = parse_utc(row.pop("blackout_start_utc"))
        row["blackout_end"] = parse_utc(row.pop("blackout_end_utc"))
        row["cooling_loss"] = _optional_time(row.pop("cooling_loss_utc"))
        row["cooling_restored"] = _optional_time(row.pop("cooling_restored_utc"))


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    return {value for value in values if value in seen or seen.add(value)}


def _is_baseline_reading(row: dict[str, Any], data: dict[str, Any]) -> bool:
    return any(
        period["refrigerator_id"] == row["refrigerator_id"]
        and period["normal_baseline"]
        and period["period_start"] <= row["timestamp"] < period["period_end"]
        for period in data["refrigerator_periods"]
    )


def _validate(data: dict[str, Any]) -> None:
    periods = data["refrigerator_periods"]
    temperatures = data["temperatures"]
    demands = data["generator_demands"]
    if duplicates := _duplicates([row["operating_period_id"] for row in periods]):
        raise DatasetError(f"Repeated operating period IDs: {sorted(duplicates)}")
    if duplicates := _duplicates([row["blackout_event_id"] for row in demands]):
        raise DatasetError(f"Repeated generator event IDs: {sorted(duplicates)}")

    refrigerator_ids = {row["refrigerator_id"] for row in periods}
    generators = {row["generator_id"] for row in periods}
    mechanical_events: dict[str, dict[str, Any]] = {}
    for row in periods:
        if row["period_start"] >= row["period_end"] or row["observed_operating_hours"] < 0:
            raise DatasetError(f"Invalid exposure period: {row['operating_period_id']}")
        event_fields = (row["failure_event_id"], row["cooling_loss"], row["cooling_restored"])
        if row["mechanical_failure"]:
            if not all(event_fields):
                raise DatasetError(f"Mechanical failure lacks event timing: {row['operating_period_id']}")
            if row["failure_event_id"] in mechanical_events:
                raise DatasetError(f"Repeated mechanical event ID: {row['failure_event_id']}")
            mechanical_events[row["failure_event_id"]] = row
        elif any(event_fields):
            raise DatasetError(f"Non-failure period has failure fields: {row['operating_period_id']}")
        if row["cooling_restored"] and row["cooling_restored"] < row["cooling_loss"]:
            raise DatasetError(f"Cooling restoration precedes loss: {row['operating_period_id']}")
        if row["normal_baseline"] and row["mechanical_failure"]:
            raise DatasetError("The documented normal baseline cannot contain a mechanical failure")
        inventory = (row["current_bags"], row["current_lot_count"], row["value_per_bag_usd"])
        if any(value is not None and value < 0 for value in inventory):
            raise DatasetError("Inventory values cannot be negative")

    for refrigerator_id in refrigerator_ids:
        intervals = sorted(
            (row["period_start"], row["period_end"], row["operating_period_id"])
            for row in periods if row["refrigerator_id"] == refrigerator_id
        )
        for previous, current in zip(intervals, intervals[1:]):
            if current[0] < previous[1]:
                raise DatasetError(f"Overlapping operating periods: {previous[2]} and {current[2]}")
        snapshots = [row for row in periods if row["refrigerator_id"] == refrigerator_id and row["current_bags"] is not None]
        if len(snapshots) != 1:
            raise DatasetError(f"Expected one current inventory row for {refrigerator_id}")
        baselines = [row for row in periods if row["refrigerator_id"] == refrigerator_id and row["normal_baseline"]]
        if len(baselines) != 1:
            raise DatasetError(f"Expected one normal baseline period for {refrigerator_id}")

    generator_failures: dict[str, dict[str, Any]] = {}
    for row in demands:
        if row["generator_id"] not in generators:
            raise DatasetError(f"Unknown generator: {row['generator_id']}")
        if row["blackout_end"] < row["blackout_start"]:
            raise DatasetError(f"Blackout ends before it starts: {row['blackout_event_id']}")
        if row["start_outcome"] not in {"success", "failure", "unknown"}:
            raise DatasetError(f"Invalid generator outcome: {row['blackout_event_id']}")
        if row["start_outcome"] == "failure":
            if not row["cooling_loss"] or not row["cooling_restored"]:
                raise DatasetError(f"Failed start lacks cooling timing: {row['blackout_event_id']}")
            if row["cooling_restored"] < row["cooling_loss"]:
                raise DatasetError(f"Cooling restoration precedes loss: {row['blackout_event_id']}")
            if row["blackout_event_id"] in mechanical_events:
                raise DatasetError(f"Failure event ID is not unique: {row['blackout_event_id']}")
            generator_failures[row["blackout_event_id"]] = row
        elif row["cooling_loss"] or row["cooling_restored"]:
            raise DatasetError(f"Non-failed demand has cooling-loss timing: {row['blackout_event_id']}")

    related_events = mechanical_events | generator_failures
    for row in temperatures:
        if row["refrigerator_id"] not in refrigerator_ids:
            raise DatasetError(f"Unknown refrigerator in temperature data: {row['refrigerator_id']}")
        if row["reading_valid"] != (row["temperature_c"] is not None):
            raise DatasetError("Valid readings require a value; invalid readings require a blank value")
        event_id = row["related_failure_event_id"]
        if event_id:
            if event_id not in related_events:
                raise DatasetError(f"Unknown related failure event: {event_id}")
            event = related_events[event_id]
            if event_id in mechanical_events and row["refrigerator_id"] != event["refrigerator_id"]:
                raise DatasetError(f"Temperature reading uses another refrigerator's event: {event_id}")
            if not event["cooling_loss"] <= row["timestamp"] <= event["cooling_restored"]:
                raise DatasetError(f"Temperature reading falls outside event {event_id}")
