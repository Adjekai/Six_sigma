from __future__ import annotations

from datetime import timedelta
from typing import Any

from .financial import summarize_financials
from .incidents import summarize_breach_and_recovery
from .reliability import generator_reliability, refrigerator_reliability
from .repository import load_scenario
from .temperature import summarize_temperature


def build_dashboard(
    scenario_id: str = "normal",
    site_id: str | None = None,
    refrigerator_id: str | None = None,
    temperature_window_hours: float = 24,
    horizon_operating_days: float = 30,
    lower_limit_c: float = 1,
    upper_limit_c: float = 6,
) -> dict[str, Any]:
    if temperature_window_hours <= 0 or horizon_operating_days <= 0:
        raise ValueError("Window and operating horizon must be greater than zero")

    data = load_scenario(scenario_id)
    reference = data["metadata"]["reference_time"]
    equipment = [row for row in data["equipment"] if site_id is None or row["site_id"] == site_id]
    if not equipment:
        raise ValueError(f"No equipment found for site {site_id}")
    equipment_ids = {row["equipment_id"] for row in equipment}

    if refrigerator_id is None:
        refrigerator_id = sorted(equipment_ids)[0]
    if refrigerator_id not in equipment_ids:
        raise ValueError(f"Unknown refrigerator in selection: {refrigerator_id}")

    window_start = reference - timedelta(hours=temperature_window_hours)
    temperatures = [row for row in data["temperatures"] if row["refrigerator_id"] in equipment_ids]
    window_temperatures = [row for row in temperatures if window_start <= row["timestamp"] <= reference]
    incidents = [row for row in data["incidents"] if row["refrigerator_id"] in equipment_ids]
    blackouts = [row for row in data["blackouts"] if site_id is None or row["site_id"] == site_id]
    inventory = [row for row in data["inventory"] if row["refrigerator_id"] in equipment_ids]

    equipment_status = []
    affected_refrigerators: set[str] = set()
    all_warnings: list[dict[str, str]] = []
    selected_summary = None
    for row in equipment:
        equipment_temperatures = [item for item in window_temperatures if item["refrigerator_id"] == row["equipment_id"]]
        summary = summarize_temperature(equipment_temperatures, reference, lower_limit_c, upper_limit_c)
        if row["equipment_id"] == refrigerator_id:
            selected_summary = summary
        unresolved = [
            incident for incident in incidents
            if incident["refrigerator_id"] == row["equipment_id"]
            and incident["cooling_loss"] <= reference <= incident["observation_end"]
            and (incident["cooling_restored"] is None or incident["cooling_restored"] > reference)
        ]
        if summary["state"] == "unknown":
            status = "unknown"
            reasons = ["Latest temperature condition is unknown"]
            affected_refrigerators.add(row["equipment_id"])
        elif unresolved:
            status = "review_required"
            reasons = ["Cooling interruption is unresolved"]
            affected_refrigerators.add(row["equipment_id"])
        elif summary["state"] in {"below_limit", "above_limit"}:
            status = "review_required"
            reasons = ["Latest temperature is outside configured limits"]
            affected_refrigerators.add(row["equipment_id"])
        else:
            status = "within_limits"
            reasons = ["Latest valid reading is within configured limits"]
        equipment_status.append(
            {
                "equipment_id": row["equipment_id"],
                "site_id": row["site_id"],
                "generator_id": row["generator_id"],
                "status": status,
                "latest_temperature_c": summary["latest_temperature_c"],
                "latest_timestamp_utc": summary["latest_timestamp_utc"],
                "freshness_minutes": summary["freshness_minutes"],
                "incident_status": "active" if unresolved else "none_active",
                "alert_reasons": reasons,
            }
        )
        all_warnings.extend(summary["warnings"])

    refrigerator_results = []
    model_groups = sorted({row["model_group"] for row in equipment})
    for model_group in model_groups:
        group_equipment = [row for row in equipment if row["model_group"] == model_group]
        group_ids = {row["equipment_id"] for row in group_equipment}
        failures = sum(
            incident["cause"] == "mechanical" and incident["refrigerator_id"] in group_ids
            for incident in incidents
        )
        exposure = sum(row["mechanical_operating_hours"] for row in group_equipment)
        result = refrigerator_reliability(failures, exposure, horizon_operating_days * 24)
        result.update({"model_group": model_group, "equipment_count": len(group_equipment)})
        refrigerator_results.append(result)
        all_warnings.extend(result["warnings"])

    generator_results = []
    for generator_id in sorted({row["generator_id"] for row in equipment}):
        demands = [row for row in blackouts if row["generator_id"] == generator_id]
        result = generator_reliability(
            failed_demands=sum(row["auto_start_outcome"] == "failure" for row in demands),
            successful_demands=sum(row["auto_start_outcome"] == "success" for row in demands),
            unknown_demands=sum(row["auto_start_outcome"] == "unknown" for row in demands),
        )
        result["generator_id"] = generator_id
        generator_results.append(result)
        all_warnings.extend(result["warnings"])

    breach_recovery = summarize_breach_and_recovery(incidents, temperatures, lower_limit_c, upper_limit_c)
    all_warnings.extend(breach_recovery["warnings"])
    mechanical_rate = refrigerator_results[0]["rate_per_hour"] if len(refrigerator_results) == 1 else None
    financial = summarize_financials(
        equipment,
        incidents,
        blackouts,
        inventory,
        affected_refrigerators,
        mechanical_rate,
    )
    all_warnings.extend(financial["warnings"])

    selected_series = [
        {
            "timestamp_utc": row["timestamp"].isoformat(),
            "temperature_c": row["temperature_c"],
            "reading_valid": row["reading_valid"],
        }
        for row in window_temperatures
        if row["refrigerator_id"] == refrigerator_id
    ]
    metadata = data["metadata"]
    return {
        "scenario": {
            "id": metadata["id"],
            "name": metadata["name"],
            "description": metadata["description"],
            "synthetic": metadata["synthetic"],
            "reference_time_utc": metadata["reference_time_utc"],
        },
        "selection": {
            "site_id": site_id,
            "refrigerator_id": refrigerator_id,
            "available_sites": sorted({row["site_id"] for row in data["equipment"]}),
            "available_refrigerators": sorted(equipment_ids),
            "temperature_window_hours": temperature_window_hours,
            "horizon_operating_days": horizon_operating_days,
        },
        "conditions": {
            "temperature_summary": selected_summary,
            "temperature_series": selected_series,
            "equipment": equipment_status,
            "inventory_exposed_usd": financial["inventory_exposed_usd"],
        },
        "reliability": {
            "refrigerators": refrigerator_results,
            "generators": generator_results,
            "breach_recovery": breach_recovery,
        },
        "financial": financial,
        "warnings": all_warnings,
    }
