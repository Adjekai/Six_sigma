from __future__ import annotations

from datetime import timedelta
from typing import Any

from .incidents import summarize_breach_and_recovery
from .financial import expected_inventory_loss
from .live_data import rejected_reading_summary
from .reliability import generator_reliability, refrigerator_reliability
from .repository import load_data
from .scenarios import SCENARIOS, load_scenario_data
from .temperature import analyze_temperature_process, forecast_temperature_limit_crossing, summarize_temperature


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
    scenario: str | None = None,
) -> dict[str, Any]:
    if temperature_window_hours <= 0 or horizon_operating_days <= 0:
        raise ValueError("Window and operating horizon must be greater than zero")

    data = load_data(include_live_readings=scenario is None)
    if scenario is not None:
        data = load_scenario_data(data, scenario)
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
    risk_forecasts = []
    process_by_refrigerator: dict[str, dict[str, Any]] = {}
    selected_summary = None
    for refrigerator in equipment:
        rows = [row for row in window_temperatures if row["refrigerator_id"] == refrigerator["equipment_id"]]
        summary = summarize_temperature(rows, reference, lower_limit_c, upper_limit_c)
        recent_rows = [
            row for row in temperatures
            if row["refrigerator_id"] == refrigerator["equipment_id"]
            and reference - timedelta(hours=2) <= row["timestamp"] <= reference
        ]
        forecast = forecast_temperature_limit_crossing(
            recent_rows, reference, lower_limit_c, upper_limit_c
        )
        baseline_period = next(
            row for row in data["refrigerator_periods"]
            if row["refrigerator_id"] == refrigerator["equipment_id"] and row["normal_baseline"]
        )
        baseline_rows_for_unit = [
            row for row in data["baseline_temperatures"]
            if row["refrigerator_id"] == refrigerator["equipment_id"]
            and baseline_period["period_start"] <= row["timestamp"] < baseline_period["period_end"]
        ]
        overall_rows_for_unit = [
            row for row in temperatures
            if row["refrigerator_id"] == refrigerator["equipment_id"]
            and row["timestamp"] >= baseline_period["period_end"]
        ]
        process_by_refrigerator[refrigerator["equipment_id"]] = analyze_temperature_process(
            rows, baseline_rows_for_unit, overall_rows_for_unit, lower_limit_c, upper_limit_c
        )
        inventory_value = (
            refrigerator["current_bags"] * refrigerator["value_per_bag_usd"]
            if refrigerator["value_per_bag_usd"] is not None else None
        )
        risk_forecast = {
            "refrigerator_id": refrigerator["equipment_id"],
            "status": forecast["status"],
            "forecast_minutes": forecast["forecast_minutes"],
            "reading_count": forecast["reading_count"],
            "slope_c_per_hour": forecast["slope_c_per_hour"],
            "predicted_minutes_to_limit": forecast["predicted_minutes_to_limit"],
            "projected_temperature_c": forecast["projected_temperature_c"],
            "as_of_utc": forecast["as_of_utc"],
            "method": "Linear fit on recent valid readings (2-hour window)",
            "control_signals": process_by_refrigerator[refrigerator["equipment_id"]]["control_signals"],
            "current_temperature_c": summary["latest_temperature_c"],
            "inventory_bags": refrigerator["current_bags"],
            "inventory_value_usd": inventory_value,
            "warnings": forecast["warnings"],
        }
        risk_forecasts.append(risk_forecast)
        all_warnings.extend(forecast["warnings"])
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
        elif refrigerator["equipment_id"] in data.get("_scenario_review_refrigerators", set()):
            status, reasons = "review_required", ["Observed synthetic scenario excursion requires review"]
        elif active or summary["state"] in {"below_limit", "above_limit"} or forecast["status"] == "approaching_limit":
            status = "review_required"
            reasons = []
            if active:
                reasons.append("Cooling interruption is active")
            if summary["state"] in {"below_limit", "above_limit"}:
                reasons.append("Latest valid temperature is outside storage limits")
            if forecast["status"] == "approaching_limit":
                reasons.append("Recent temperature trend projects a storage-limit crossing")
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
                "temperature_risk_status": forecast["status"],
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

    group_failure_probability = {row["model_group"]: row["failure_probability"] for row in refrigerator_results}
    for forecast in risk_forecasts:
        equipment_row = next(row for row in equipment if row["equipment_id"] == forecast["refrigerator_id"])
        f30 = group_failure_probability.get(equipment_row["model_group"])
        signals = forecast["control_signals"]
        latest = forecast["current_temperature_c"]
        out_of_range = latest is not None and (latest < lower_limit_c or latest > upper_limit_c)
        if out_of_range:
            banner = "At risk"
            reason = "Latest reading is outside the configured range"
        elif forecast["status"] == "approaching_limit":
            banner = "Watch"
            reason = "Linear estimate projects a limit crossing within 60 minutes"
        elif signals:
            banner = "Watch"
            reason = f"Control-chart signal: {signals[-1]['rule']}"
        elif f30 is not None and f30 >= 0.10:
            banner = "Watch"
            reason = f"Pooled constant-rate F(30 d) estimate is {f30:.1%}"
        elif latest is None or forecast["status"] in {"unknown", "insufficient_data"}:
            banner = "Watch"
            reason = "Latest condition or trend is not known"
        else:
            banner = "In range"
            reason = f"Latest reading is within range; pooled F(30 d) estimate {f30:.1%}" if f30 is not None else "Latest reading is within range"
        forecast["decision_support_status"] = banner
        forecast["decision_support_reason"] = reason
        forecast["failure_probability_30d"] = f30

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
        row for row in data["baseline_temperatures"]
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
    process_analysis["autocorrelation_note"] = "Readings are autocorrelated; normal-theory capability estimates are descriptive."
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
    result = {
        "dataset": {
            "name": "Blood bank equipment history",
            "synthetic": True,
            "live_reading_count": data["live_reading_count"],
            "reference_time_utc": reference.isoformat(),
            "rejected_readings": rejected_reading_summary(),
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
            "risk_forecasts": risk_forecasts,
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
        "financial_estimates": {
            "refrigerators": [
                {
                    "refrigerator_id": row["equipment_id"],
                    "expected_loss_30d_usd": expected_inventory_loss(
                        next((item["failure_probability"] for item in refrigerator_results if item["model_group"] == row["model_group"]), None),
                        row["current_bags"] * row["value_per_bag_usd"] if row["value_per_bag_usd"] is not None else None,
                    ),
                }
                for row in equipment
            ],
            "generator_expected_loss_per_blackout_usd": (
                generator_results[0]["failed_start_probability"] * 252000 if generator_results and generator_results[0]["failed_start_probability"] is not None else None
            ),
            "generator_wilson_upper_case_usd": (
                generator_results[0]["wilson_interval_95"]["upper"] * 252000 if generator_results and generator_results[0]["wilson_interval_95"]["upper"] is not None else None
            ),
        },
        "warnings": all_warnings,
    }
    if scenario is not None:
        scenario_info = {
            "id": scenario,
            **SCENARIOS[scenario],
            "synthetic_data": True,
            "observed_alarm": None,
        }
        if scenario in {"degrading_refrigerator", "blackout_failed_generator"}:
            event_id = "SIM-RF-001" if scenario == "degrading_refrigerator" else "SIM-GF-001"
            event = next(
                row for row in breach_recovery["incidents"]
                if row["failure_event_id"] == event_id
                and row["refrigerator_id"] == ("R1" if scenario == "degrading_refrigerator" else refrigerator_id)
            )
            affected_inventory = next(
                row for row in inventory_rows if row["refrigerator_id"] == event["refrigerator_id"]
            )
            scenario_info["observed_alarm"] = {
                "status": "review_required" if event["breach_status"] == "breached" else event["breach_status"],
                "event_id": event_id,
                "refrigerator_id": event["refrigerator_id"],
                "cause": event["cause"],
                "first_breach_utc": event["first_breach_utc"],
                "hours_to_first_breach": event["observed_hours_to_breach_or_censoring"],
                "excursion_duration_hours": (
                    event["recovery_hours"] - event["observed_hours_to_breach_or_censoring"]
                    if event["breach_status"] == "breached" and event["recovery_hours"] is not None
                    else None
                ),
                "recovery_hours": event["recovery_hours"],
                "affected_inventory_value_usd": affected_inventory["inventory_value_usd"],
            }
            if scenario == "blackout_failed_generator":
                demand = next(row for row in data["generator_demands"] if row["blackout_event_id"] == event_id)
                scenario_info["observed_alarm"]["outage_duration_hours"] = (
                    demand["blackout_end"] - demand["blackout_start"]
                ).total_seconds() / 3600
        result["scenario"] = scenario_info
    return result
