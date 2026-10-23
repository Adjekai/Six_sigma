from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any


SCENARIOS = {
    "stable": {
        "label": "Stable",
        "description": "Steady power and temperatures within the configured 1–6 °C range.",
    },
    "degrading_refrigerator": {
        "label": "Degrading Refrigerator",
        "description": "A planted temperature excursion requires review of Refrigerator R1 and its recorded inventory value.",
    },
    "blackout_failed_generator": {
        "label": "Blackout with Failed Generator",
        "description": "A synthetic outage and failed generator start produce an observed cooling alarm.",
    },
}


def scenario_options() -> list[dict[str, str]]:
    return [{"id": key, **value} for key, value in SCENARIOS.items()]


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
    for refrigerator_index, refrigerator_id in enumerate(sorted({row["refrigerator_id"] for row in data["refrigerator_periods"]})):
        timestamp = baseline["period_start"]
        index = 0
        while timestamp < baseline["period_end"]:
            temperature = 3.9 + ((index + refrigerator_index) % 5) * 0.05
            temperatures.append(_temperature(timestamp, refrigerator_id, temperature))
            timestamp += timedelta(minutes=15)
            index += 1
        timestamp = reference - timedelta(hours=24)
        while timestamp <= reference:
            temperature = 3.9 + ((index + refrigerator_index) % 5) * 0.05
            temperatures.append(_temperature(timestamp, refrigerator_id, temperature))
            timestamp += timedelta(minutes=15)
            index += 1
    data["temperatures"] = temperatures
    data["reference_time"] = reference
    data["_scenario_review_refrigerators"] = set()
    return data


def _temperature(timestamp: Any, refrigerator_id: str, temperature: float, event_id: str | None = None) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "refrigerator_id": refrigerator_id,
        "temperature_c": temperature,
        "reading_valid": True,
        "related_failure_event_id": event_id,
    }


def _event_data(source: dict[str, Any], scenario: str) -> dict[str, Any]:
    data = deepcopy(source)
    reference = source["reference_time"] + timedelta(hours=12)
    loss = reference - timedelta(hours=5)
    if scenario == "degrading_refrigerator":
        event_id = "DEMO-RF-001"
        restored = reference - timedelta(hours=2)
        refrigerator_id = "R1"
        data["refrigerator_periods"].append(
            {
                "operating_period_id": "OP-R1-DEMO",
                "refrigerator_id": refrigerator_id,
                "site_id": "BLOOD-BANK-1",
                "model_group": "CW-100",
                "generator_id": "G1",
                "period_start": loss,
                "period_end": restored + timedelta(hours=1),
                "observed_operating_hours": 4.0,
                "mechanical_failure": True,
                "failure_event_id": event_id,
                "cooling_loss": loss,
                "cooling_restored": restored,
                "normal_baseline": False,
                "current_bags": None,
                "current_lot_count": None,
                "value_per_bag_usd": None,
            }
        )
    else:
        event_id = "DEMO-GF-001"
        restored = reference - timedelta(hours=1)
        refrigerator_id = None
        data["generator_demands"].append(
            {
                "blackout_event_id": event_id,
                "generator_id": "G1",
                "site_id": "BLOOD-BANK-1",
                "blackout_start": loss,
                "blackout_end": loss + timedelta(hours=1),
                "start_outcome": "failure",
                "cooling_loss": loss,
                "cooling_restored": restored,
            }
        )

    data["reference_time"] = reference
    event_by_refrigerator = {refrigerator_id} if refrigerator_id else {"R1", "R2", "R3"}
    new_readings = []
    timestamp = source["reference_time"] + timedelta(minutes=15)
    while timestamp <= reference:
        elapsed = (timestamp - loss).total_seconds() / 3600
        for current_id in sorted({row["refrigerator_id"] for row in data["refrigerator_periods"]}):
            related = current_id in event_by_refrigerator and loss <= timestamp <= restored
            if related:
                if timestamp == restored:
                    value = 4.1
                elif elapsed < 1:
                    value = 4.2 + elapsed * 0.7
                else:
                    value = 4.9 + (elapsed - 1) * 0.85
                # Keep the blackout gradual and make the refrigerator excursion cross 6 °C visibly.
                if scenario == "blackout_failed_generator":
                    value = 4.2 + min(max(elapsed, 0), 3.75) * 0.8 if timestamp != restored else 4.1
                value = round(value, 2)
            else:
                value = round(3.9 + ((timestamp.minute // 15 + len(current_id)) % 5) * 0.05, 2)
            new_readings.append(_temperature(timestamp, current_id, value, event_id if related else None))
        timestamp += timedelta(minutes=15)
    data["temperatures"].extend(new_readings)
    data["_scenario_review_refrigerators"] = event_by_refrigerator
    return data


def load_scenario_data(source: dict[str, Any], scenario: str) -> dict[str, Any]:
    if scenario not in SCENARIOS:
        choices = ", ".join(SCENARIOS)
        raise ValueError(f"Unknown demo scenario: {scenario}. Choose one of: {choices}")
    if scenario == "stable":
        return _stable_data(source)
    return _event_data(source, scenario)
