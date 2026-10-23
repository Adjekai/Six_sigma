from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any


SCENARIOS = {
    "stable": {
        "label": "Stable conditions",
        "description": "Steady power and temperatures within the configured 1–6 °C range.",
    },
    "degrading_refrigerator": {
        "label": "Degrading refrigerator",
        "description": "A planted temperature excursion affects Refrigerator R1 and its recorded inventory.",
    },
    "blackout_failed_generator": {
        "label": "Blackout with failed generator",
        "description": "A synthetic outage and failed generator start produce observed cooling alarms.",
    },
}


def scenario_options() -> list[dict[str, str]]:
    return [{"id": key, **value} for key, value in SCENARIOS.items()]


def _temperature(
    timestamp: Any,
    refrigerator_id: str,
    temperature_c: float,
    event_id: str | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "refrigerator_id": refrigerator_id,
        "temperature_c": temperature_c,
        "reading_valid": True,
        "related_failure_event_id": event_id,
    }


def _stable_data(source: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(source)
    for period in data["refrigerator_periods"]:
        period["mechanical_failure"] = False
        period["failure_event_id"] = None
        period["cooling_loss"] = None
        period["cooling_restored"] = None
    for demand in data["generator_demands"]:
        demand["start_outcome"] = "success"
        demand["cooling_loss"] = None
        demand["cooling_restored"] = None

    baseline = next(row for row in data["refrigerator_periods"] if row["normal_baseline"])
    reference = source["reference_time"] + timedelta(days=1)
    temperatures = []
    refrigerator_ids = sorted({row["refrigerator_id"] for row in data["refrigerator_periods"]})
    for refrigerator_index, refrigerator_id in enumerate(refrigerator_ids):
        timestamp = baseline["period_start"]
        index = 0
        while timestamp < baseline["period_end"]:
            value = 3.9 + ((index + refrigerator_index) % 5) * 0.05
            temperatures.append(_temperature(timestamp, refrigerator_id, value))
            timestamp += timedelta(minutes=15)
            index += 1
        timestamp = reference - timedelta(hours=24)
        while timestamp <= reference:
            value = 3.9 + ((index + refrigerator_index) % 5) * 0.05
            temperatures.append(_temperature(timestamp, refrigerator_id, value))
            timestamp += timedelta(minutes=15)
            index += 1

    data["temperatures"] = temperatures
    data["reference_time"] = reference
    data["_scenario_review_refrigerators"] = set()
    return data


def _event_data(source: dict[str, Any], scenario: str) -> dict[str, Any]:
    data = deepcopy(source)
    reference = source["reference_time"] + timedelta(hours=12)
    cooling_loss = reference - timedelta(hours=5)
    if scenario == "degrading_refrigerator":
        event_id = "DEMO-RF-001"
        restored = reference - timedelta(hours=2)
        affected_refrigerator = "R1"
        data["refrigerator_periods"].append(
            {
                "operating_period_id": "OP-R1-DEMO",
                "refrigerator_id": affected_refrigerator,
                "site_id": "BLOOD-BANK-1",
                "model_group": "CW-100",
                "generator_id": "G1",
                "period_start": cooling_loss,
                "period_end": restored + timedelta(hours=1),
                "observed_operating_hours": 4.0,
                "mechanical_failure": True,
                "failure_event_id": event_id,
                "cooling_loss": cooling_loss,
                "cooling_restored": restored,
                "normal_baseline": False,
                "current_bags": None,
                "current_lot_count": None,
                "value_per_bag_usd": None,
            }
        )
        affected_refrigerators = {affected_refrigerator}
    else:
        event_id = "DEMO-GF-001"
        restored = reference - timedelta(hours=1)
        affected_refrigerator = None
        data["generator_demands"].append(
            {
                "blackout_event_id": event_id,
                "generator_id": "G1",
                "site_id": "BLOOD-BANK-1",
                "blackout_start": cooling_loss,
                "blackout_end": cooling_loss + timedelta(hours=1),
                "start_outcome": "failure",
                "cooling_loss": cooling_loss,
                "cooling_restored": restored,
            }
        )
        affected_refrigerators = {"R1", "R2", "R3"}

    data["reference_time"] = reference
    new_readings = []
    timestamp = source["reference_time"] + timedelta(minutes=15)
    while timestamp <= reference:
        elapsed = (timestamp - cooling_loss).total_seconds() / 3600
        for refrigerator_id in sorted({row["refrigerator_id"] for row in data["refrigerator_periods"]}):
            related = refrigerator_id in affected_refrigerators and cooling_loss <= timestamp <= restored
            if related:
                if timestamp == restored:
                    value = 4.1
                elif scenario == "blackout_failed_generator":
                    value = 4.2 + min(max(elapsed, 0), 3.75) * 0.8
                elif elapsed < 1:
                    value = 4.2 + elapsed * 0.7
                else:
                    value = 4.9 + (elapsed - 1) * 0.85
                value = round(value, 2)
            else:
                value = round(3.9 + ((timestamp.minute // 15 + len(refrigerator_id)) % 5) * 0.05, 2)
            new_readings.append(_temperature(timestamp, refrigerator_id, value, event_id if related else None))
        timestamp += timedelta(minutes=15)

    data["temperatures"].extend(new_readings)
    data["_scenario_review_refrigerators"] = affected_refrigerators
    return data


def load_scenario_data(source: dict[str, Any], scenario: str) -> dict[str, Any]:
    if scenario not in SCENARIOS:
        choices = ", ".join(SCENARIOS)
        raise ValueError(f"Unknown demo scenario: {scenario}. Choose one of: {choices}")
    if scenario == "stable":
        return _stable_data(source)
    return _event_data(source, scenario)