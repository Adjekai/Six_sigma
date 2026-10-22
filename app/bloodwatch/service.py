from __future__ import annotations

from datetime import timedelta
from typing import Any

from .incidents import summarize_breach_and_recovery
from .reliability import generator_reliability, refrigerator_reliability
from .repository import load_data
from .temperature import analyze_temperature_process, summarize_temperature


def _equipment(periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for refrigerator_id in sorted({row["refrigerator_id"] for row in periods}):
        rows = [row for row in periods if row["refrigerator_id"] == refrigerator_id]
        snapshot = next(row for row in rows if row["current_bags"] is not None)
        result.append(
            {
                "equipment_id": refrigerator_id,
                "site_id": snapshot["site_id"],
                "model_group": snapshot["model_group"],
                "generator_id": snapshot["generator_id"],
                "mechanical_operating_hours": sum(row["observed_operating_hours"] for row in rows),
                "current_bags": snapshot["current_bags"],
                "current_lot_count": snapshot["current_lot_count"],
                "value_per_bag_usd": snapshot["value_per_bag_usd"],
            }
        )
    return result


def _incidents(data: dict[str, Any], equipment: list[dict[str, Any]]) -> list[dict[str, Any]]:
    incidents = []
    for row in data["refrigerator_periods"]:
        if row["mechanical_failure"]:
            incidents.append(
                {
                    "incident_id": row["failure_event_id"],
                    "failure_event_id": row["failure_event_id"],
                    "refrigerator_id": row["refrigerator_id"],
                    "cause": "mechanical",
                    "cooling_loss": row["cooling_loss"],
                    "observation_end": row["cooling_restored"],
                    "cooling_restored": row["cooling_restored"],
                }
            )
    for demand in data["generator_demands"]:
        if demand["start_outcome"] != "failure":
            continue
        for refrigerator in equipment:
            if refrigerator["generator_id"] == demand["generator_id"]:
                incidents.append(
                    {
                        "incident_id": f"{demand['blackout_event_id']}-{refrigerator['equipment_id']}",
                        "failure_event_id": demand["blackout_event_id"],
                        "refrigerator_id": refrigerator["equipment_id"],
                        "cause": "generator_failed_start",
                        "cooling_loss": demand["cooling_loss"],
                        "observation_end": demand["cooling_restored"],
                        "cooling_restored": demand["cooling_restored"],
                    }
                )
    return incidents


def build_dashboard(
    refrigerator_id: str | None = None,
    temperature_window_hours: float = 24,
    horizon_operating_days: float = 30,
    lower_limit_c: float = 1,
    upper_limit_c: float = 6,
) -> dict[str, Any]:
    if temperature_window_hours <= 0 or horizon_operating_days <= 0:
        raise ValueError("Window and operating horizon must be greater than zero")

    data = load_data()
    reference = data["reference_time"]
    equipment = _equipment(data["refrigerator_periods"])
    equipment_ids = {row["equipment_id"] for row in equipment}
    refrigerator_id = refrigerator_id or sorted(equipment_ids)[0]
    if refrigerator_id not in equipment_ids:
        raise ValueError(f"Unknown refrigerator in selection: {refrigerator_id}")

    window_start = reference - timedelta(hours=temperature_window_hours)
    temperatures = data["temperatures"]
    window_temperatures = [row for row in temperatures if window_start <= row["timestamp"] <= reference]
    incidents = _incidents(data, equipment)
    current_incidents = [row for row in incidents if row["cooling_loss"] >= reference - timedelta(hours=24)]
    all_warnings: list[dict[str, str]] = []

    equipment_status = []
    selected_summary = None
    for refrigerator in equipment:
        rows = [row for row in window_temperatures if row["refrigerator_id"] == refrigerator["equipment_id"]]
        summary = summarize_temperature(rows, reference, lower_limit_c, upper_limit_c)
        if refrigerator["equipment_id"] == refrigerator_id:
            selected_summary = summary
        active = [
            incident for incident in current_incidents
            if incident["refrigerator_id"] == refrigerator["equipment_id"]
            and incident["cooling_loss"] <= reference
            and (incident["cooling_restored"] is None or incident["cooling_restored"] > reference)
        ]
        if summary["state"] == "unknown":
            status, reasons = "unknown", ["Latest temperature condition is unknown"]
        elif active or summary["state"] in {"below_limit", "above_limit"}:
            status, reasons = "review_required", ["Cooling or temperature requires review"]
        else:
            status, reasons = "within_limits", ["Latest valid reading is within configured limits"]
        equipment_status.append(
            {
                "equipment_id": refrigerator["equipment_id"],
                "site_id": refrigerator["site_id"],
                "generator_id": refrigerator["generator_id"],
                "status": status,
                "latest_temperature_c": summary["latest_temperature_c"],
                "latest_timestamp_utc": summary["latest_timestamp_utc"],
                "freshness_minutes": summary["freshness_minutes"],
                "incident_status": "active" if active else "none_active",
                "alert_reasons": reasons,
            }
        )
        all_warnings.extend(summary["warnings"])

    refrigerator_results = []
    for model_group in sorted({row["model_group"] for row in equipment}):
        group = [row for row in equipment if row["model_group"] == model_group]
        group_ids = {row["equipment_id"] for row in group}
        failures = sum(
            row["mechanical_failure"] and row["refrigerator_id"] in group_ids
            for row in data["refrigerator_periods"]
        )
        exposure = sum(row["mechanical_operating_hours"] for row in group)
        result = refrigerator_reliability(failures, exposure, horizon_operating_days * 24)
        result.update({"model_group": model_group, "equipment_count": len(group)})
        refrigerator_results.append(result)
        all_warnings.extend(result["warnings"])

    generator_results = []
    for generator_id in sorted({row["generator_id"] for row in equipment}):
        demands = [row for row in data["generator_demands"] if row["generator_id"] == generator_id]
        result = generator_reliability(
            failed_demands=sum(row["start_outcome"] == "failure" for row in demands),
            successful_demands=sum(row["start_outcome"] == "success" for row in demands),
            unknown_demands=sum(row["start_outcome"] == "unknown" for row in demands),
        )
        result["generator_id"] = generator_id
        generator_results.append(result)
        all_warnings.extend(result["warnings"])

    breach_recovery = summarize_breach_and_recovery(incidents, temperatures, lower_limit_c, upper_limit_c)
    all_warnings.extend(breach_recovery["warnings"])
    selected_incidents = [row for row in incidents if row["refrigerator_id"] == refrigerator_id]
    selected_breach = summarize_breach_and_recovery(selected_incidents, temperatures, lower_limit_c, upper_limit_c)

    selected_rows = [row for row in window_temperatures if row["refrigerator_id"] == refrigerator_id]
    baseline_period = next(
        row for row in data["refrigerator_periods"]
        if row["refrigerator_id"] == refrigerator_id and row["normal_baseline"]
    )
    baseline_rows = [
        row for row in temperatures
        if row["refrigerator_id"] == refrigerator_id
        and baseline_period["period_start"] <= row["timestamp"] < baseline_period["period_end"]
    ]
    overall_rows = [
        row for row in temperatures
        if row["refrigerator_id"] == refrigerator_id and row["timestamp"] >= baseline_period["period_end"]
    ]
    process_analysis = analyze_temperature_process(
        selected_rows, baseline_rows, overall_rows, lower_limit_c, upper_limit_c
    )
    process_analysis.update(
        {
            "baseline_start_utc": baseline_period["period_start"].isoformat(),
            "baseline_end_utc": baseline_period["period_end"].isoformat(),
        }
    )

    inventory_rows = []
    for row in equipment:
        value = row["current_bags"] * row["value_per_bag_usd"] if row["value_per_bag_usd"] is not None else None
        inventory_rows.append(
            {
                "refrigerator_id": row["equipment_id"],
                "bags_present": row["current_bags"],
                "lot_count": row["current_lot_count"],
                "inventory_value_usd": value,
            }
        )
    selected_equipment = next(row for row in equipment if row["equipment_id"] == refrigerator_id)
    selected_series = [
        {
            "timestamp_utc": row["timestamp"].isoformat(),
            "temperature_c": row["temperature_c"],
            "reading_valid": row["reading_valid"],
            "related_failure_event_id": row["related_failure_event_id"],
        }
        for row in selected_rows
    ]
    return {
        "dataset": {
            "name": "Blood bank equipment history",
            "synthetic": True,
            "reference_time_utc": reference.isoformat(),
        },
        "selection": {
            "refrigerator_id": refrigerator_id,
            "available_refrigerators": sorted(equipment_ids),
            "temperature_window_hours": temperature_window_hours,
            "horizon_operating_days": horizon_operating_days,
        },
        "conditions": {
            "temperature_summary": selected_summary,
            "temperature_series": selected_series,
            "equipment": equipment_status,
            "inventory_summary": {
                "bags_present": sum(row["bags_present"] for row in inventory_rows),
                "lot_count": sum(row["lot_count"] for row in inventory_rows),
                "inventory_value_usd": sum(row["inventory_value_usd"] or 0 for row in inventory_rows),
                "unknown_value_lot_count": sum(row["inventory_value_usd"] is None for row in inventory_rows),
                "as_of_utc": reference.isoformat(),
                "by_refrigerator": inventory_rows,
            },
            "process_analysis": process_analysis,
        },
        "reliability": {
            "refrigerators": refrigerator_results,
            "generators": generator_results,
            "breach_recovery": breach_recovery,
            "selected_refrigerator_model": next(
                row for row in refrigerator_results if row["model_group"] == selected_equipment["model_group"]
            ),
            "selected_generator": next(
                row for row in generator_results if row["generator_id"] == selected_equipment["generator_id"]
            ),
            "selected_breach_recovery": selected_breach,
        },
        "warnings": all_warnings,
    }
