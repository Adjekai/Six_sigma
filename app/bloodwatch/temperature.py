from __future__ import annotations

from datetime import datetime
from math import sqrt
from statistics import mean, stdev
from typing import Any

from .common import warning


def analyze_temperature_process(
    displayed_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    overall_rows: list[dict[str, Any]],
    lower_limit_c: float = 1.0,
    upper_limit_c: float = 6.0,
) -> dict[str, Any]:
    displayed = sorted(
        (row for row in displayed_rows if row["reading_valid"] and row["temperature_c"] is not None),
        key=lambda row: row["timestamp"],
    )
    baseline = sorted(
        (row for row in baseline_rows if row["reading_valid"] and row["temperature_c"] is not None),
        key=lambda row: row["timestamp"],
    )
    overall = sorted(
        (row for row in overall_rows if row["reading_valid"] and row["temperature_c"] is not None),
        key=lambda row: row["timestamp"],
    )
    displayed_values = [row["temperature_c"] for row in displayed]
    baseline_values = [row["temperature_c"] for row in baseline]
    overall_values = [row["temperature_c"] for row in overall]
    result: dict[str, Any] = {
        "baseline_source": "documented_normal_operation",
        "baseline_count": len(baseline_values),
        "overall_count": len(overall_values),
        "standard_error_c": stdev(displayed_values) / sqrt(len(displayed_values)) if len(displayed_values) > 1 else None,
        "center_line_c": None,
        "lower_control_limit_c": None,
        "upper_control_limit_c": None,
        "out_of_control_count": None,
        "within_sigma_c": None,
        "cp": None,
        "cpk": None,
        "pp": None,
        "ppk": None,
        "capability_status": "unsupported",
        "capability_explanation": "At least two valid baseline readings are required.",
    }
    if len(baseline_values) < 2:
        return result

    moving_ranges = [abs(current - previous) for previous, current in zip(baseline_values, baseline_values[1:])]
    within_sigma = mean(moving_ranges) / 1.128
    center = mean(baseline_values)
    lower_control = center - 3 * within_sigma
    upper_control = center + 3 * within_sigma
    overall_sigma = stdev(overall_values) if len(overall_values) > 1 else None
    result.update(
        {
            "center_line_c": center,
            "lower_control_limit_c": lower_control,
            "upper_control_limit_c": upper_control,
            "out_of_control_count": sum(value < lower_control or value > upper_control for value in displayed_values),
            "within_sigma_c": within_sigma,
        }
    )
    if within_sigma > 0:
        result["cp"] = (upper_limit_c - lower_limit_c) / (6 * within_sigma)
        result["cpk"] = min(
            (upper_limit_c - center) / (3 * within_sigma),
            (center - lower_limit_c) / (3 * within_sigma),
        )
        result["capability_status"] = "estimated"
        result["capability_explanation"] = "Cp/Cpk use the fixed normal baseline; Pp/Ppk use the complete operational temperature history."
    else:
        result["capability_explanation"] = "Capability is unsupported because the baseline has no measurable variation."
    if overall_sigma and overall_sigma > 0:
        overall_mean = mean(overall_values)
        result["pp"] = (upper_limit_c - lower_limit_c) / (6 * overall_sigma)
        result["ppk"] = min(
            (upper_limit_c - overall_mean) / (3 * overall_sigma),
            (overall_mean - lower_limit_c) / (3 * overall_sigma),
        )
    elif len(overall_values) < 2:
        result["capability_status"] = "unsupported"
        result["capability_explanation"] = "Pp/Ppk require at least two valid overall observations."
    else:
        result["capability_status"] = "unsupported"
        result["capability_explanation"] = "Pp/Ppk are unsupported because the overall history has no measurable variation."
    return result


def summarize_temperature(
    rows: list[dict[str, Any]],
    reference_time: datetime,
    lower_limit_c: float = 1.0,
    upper_limit_c: float = 6.0,
    stale_after_minutes: float = 30.0,
) -> dict[str, Any]:
    if lower_limit_c >= upper_limit_c:
        raise ValueError("lower_limit_c must be below upper_limit_c")
    valid = [row for row in rows if row["reading_valid"] and row["temperature_c"] is not None]
    result: dict[str, Any] = {
        "latest_temperature_c": None,
        "latest_timestamp_utc": None,
        "freshness_minutes": None,
        "minimum_c": None,
        "maximum_c": None,
        "mean_c": None,
        "standard_deviation_c": None,
        "valid_count": len(valid),
        "missing_or_invalid_count": len(rows) - len(valid),
        "state": "unknown",
        "lower_limit_c": lower_limit_c,
        "upper_limit_c": upper_limit_c,
        "warnings": [],
    }
    if not valid:
        result["warnings"].append(warning("NO_VALID_TEMPERATURE", "No valid readings are available in the selected window."))
        return result

    valid.sort(key=lambda row: row["timestamp"])
    latest = valid[-1]
    freshness = (reference_time - latest["timestamp"]).total_seconds() / 60
    values = [row["temperature_c"] for row in valid]
    result.update(
        {
            "latest_temperature_c": latest["temperature_c"],
            "latest_timestamp_utc": latest["timestamp"].isoformat(),
            "freshness_minutes": freshness,
            "minimum_c": min(values),
            "maximum_c": max(values),
            "mean_c": mean(values),
            "standard_deviation_c": stdev(values) if len(values) > 1 else None,
        }
    )
    if freshness > stale_after_minutes:
        result["state"] = "unknown"
        result["warnings"].append(warning("STALE_TEMPERATURE", "The latest valid reading is stale."))
    elif latest["temperature_c"] < lower_limit_c:
        result["state"] = "below_limit"
    elif latest["temperature_c"] > upper_limit_c:
        result["state"] = "above_limit"
    else:
        result["state"] = "within_limits"
    return result


def forecast_temperature_limit_crossing(
    rows: list[dict[str, Any]],
    reference_time: datetime,
    lower_limit_c: float = 1.0,
    upper_limit_c: float = 6.0,
    forecast_minutes: float = 60.0,
    stale_after_minutes: float = 30.0,
    minimum_readings: int = 4,
    minimum_span_minutes: float = 30.0,
) -> dict[str, Any]:
    valid = sorted(
        (row for row in rows if row["reading_valid"] and row["temperature_c"] is not None),
        key=lambda row: row["timestamp"],
    )
    result: dict[str, Any] = {
        "status": "insufficient_data",
        "forecast_minutes": forecast_minutes,
        "reading_count": len(valid),
        "slope_c_per_hour": None,
        "predicted_minutes_to_limit": None,
        "projected_temperature_c": None,
        "warnings": [],
    }
    if len(valid) < minimum_readings:
        result["warnings"].append(warning("FORECAST_INSUFFICIENT_READINGS", "Not enough recent valid readings to estimate a temperature trend.", "info"))
        return result

    latest = valid[-1]
    age_minutes = (reference_time - latest["timestamp"]).total_seconds() / 60
    span_minutes = (latest["timestamp"] - valid[0]["timestamp"]).total_seconds() / 60
    if age_minutes < 0 or age_minutes > stale_after_minutes:
        result["status"] = "unknown"
        result["warnings"].append(warning("FORECAST_STALE_READINGS", "Recent temperature readings are stale; no trend forecast is available."))
        return result
    if span_minutes < minimum_span_minutes:
        result["warnings"].append(warning("FORECAST_SHORT_HISTORY", "Recent readings do not span enough time to estimate a temperature trend.", "info"))
        return result

    current = float(latest["temperature_c"])
    if current < lower_limit_c or current > upper_limit_c:
        result.update({"status": "currently_out_of_range", "projected_temperature_c": current})
        return result

    elapsed = [(row["timestamp"] - latest["timestamp"]).total_seconds() / 60 for row in valid]
    values = [float(row["temperature_c"]) for row in valid]
    mean_elapsed = mean(elapsed)
    mean_value = mean(values)
    denominator = sum((value - mean_elapsed) ** 2 for value in elapsed)
    if denominator == 0:
        result["warnings"].append(warning("FORECAST_NO_TIME_VARIATION", "Readings have no timestamp variation; no trend forecast is available.", "info"))
        return result
    slope_per_minute = sum((time - mean_elapsed) * (value - mean_value) for time, value in zip(elapsed, values)) / denominator
    slope_per_hour = slope_per_minute * 60
    projected = current + slope_per_minute * forecast_minutes
    crossing_minutes = None
    if slope_per_minute > 0 and projected > upper_limit_c:
        crossing_minutes = (upper_limit_c - current) / slope_per_minute
    elif slope_per_minute < 0 and projected < lower_limit_c:
        crossing_minutes = (lower_limit_c - current) / slope_per_minute

    status = "approaching_limit" if crossing_minutes is not None else "within_limits"
    result.update(
        {
            "status": status,
            "slope_c_per_hour": slope_per_hour,
            "predicted_minutes_to_limit": crossing_minutes,
            "projected_temperature_c": projected,
        }
    )
    if crossing_minutes is not None:
        result["warnings"].append(
            warning(
                "PREDICTED_STORAGE_LIMIT_CROSSING",
                f"Recent temperature trend projects crossing the storage limit in about {crossing_minutes:.0f} minutes; verify the sensor and inspect cooling equipment.",
            )
        )
    return result
