from __future__ import annotations

from datetime import datetime
from math import erf, sqrt
from statistics import mean, stdev
from typing import Any
from scipy.stats import shapiro

from .common import warning

MIN_CAPABILITY_N = 100


def analyze_temperature_process(
    displayed_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    overall_rows: list[dict[str, Any]],
    lower_limit_c: float = 1.0,
    upper_limit_c: float = 6.0,
) -> dict[str, Any]:
    displayed_sequence = sorted(displayed_rows, key=lambda row: row["timestamp"])
    displayed = [
        row for row in displayed_sequence
        if row["reading_valid"] and row["temperature_c"] is not None
    ]
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
        "moving_range_average_c": None,
        "moving_range_ucl_c": None,
        "moving_range_series": [],
        "control_signals": [],
        "observed_out_of_spec_percent": (
            100 * sum(value < lower_limit_c or value > upper_limit_c for value in overall_values) / len(overall_values)
            if overall_values else None
        ),
        "normal_theory_out_of_spec_percent": None,
        "normality_p_value": None,
        "normality_sample_count": min(len(overall_values), 5000),
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
    mrbar = mean(moving_ranges)
    lower_control = center - 2.66 * mrbar
    upper_control = center + 2.66 * mrbar
    overall_sigma = stdev(overall_values) if len(overall_values) > 1 else None
    result.update(
        {
            "center_line_c": center,
            "lower_control_limit_c": lower_control,
            "upper_control_limit_c": upper_control,
            "out_of_control_count": sum(value < lower_control or value > upper_control for value in displayed_values),
            "within_sigma_c": within_sigma,
            "moving_range_average_c": mrbar,
            "moving_range_ucl_c": 3.267 * mrbar,
            "moving_range_series": [
                {"timestamp_utc": baseline[index + 1]["timestamp"].isoformat(), "moving_range_c": value}
                for index, value in enumerate(moving_ranges)
            ],
        }
    )
    signals = []
    sequence_values = [
        row["temperature_c"] if row["reading_valid"] and row["temperature_c"] is not None else None
        for row in displayed_sequence
    ]
    def control_signal(start: int, end: int, rule: str) -> dict[str, Any]:
        points = [
            {
                "timestamp_utc": displayed_sequence[index]["timestamp"].isoformat(),
                "temperature_c": sequence_values[index],
            }
            for index in range(start, end + 1)
            if sequence_values[index] is not None
        ]
        return {
            "index": end,
            "start_index": start,
            "end_index": end,
            "value_c": sequence_values[end],
            "rule": rule,
            "start_timestamp_utc": points[0]["timestamp_utc"],
            "timestamp_utc": points[-1]["timestamp_utc"],
            "points": points,
        }

    for index, value in enumerate(sequence_values):
        if value is not None and (value < lower_control or value > upper_control):
            signals.append(control_signal(index, index, "3-sigma control limit"))
    for end in range(7, len(sequence_values)):
        window = sequence_values[end - 7:end + 1]
        if any(value is None for value in window):
            continue
        if all(value > center for value in window) or all(value < center for value in window):
            signals.append(control_signal(end - 7, end, "8 consecutive points on one side"))
    for end in range(5, len(sequence_values)):
        window = sequence_values[end - 5:end + 1]
        if any(value is None for value in window):
            continue
        if all(a < b for a, b in zip(window, window[1:])) or all(a > b for a, b in zip(window, window[1:])):
            signals.append(control_signal(end - 5, end, "6 consecutive points steadily increasing or decreasing"))
    result["control_signals"] = signals
    if within_sigma > 0:
        result["cp"] = (upper_limit_c - lower_limit_c) / (6 * within_sigma)
        result["cpk"] = min(
            (upper_limit_c - center) / (3 * within_sigma),
            (center - lower_limit_c) / (3 * within_sigma),
        )
        result["capability_status"] = "estimated" if len(overall_values) >= MIN_CAPABILITY_N else "insufficient_data"
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
        overall_mean = mean(overall_values)
        cdf = lambda x: 0.5 * (1 + erf((x - overall_mean) / (overall_sigma * sqrt(2))))
        result["normal_theory_out_of_spec_percent"] = 100 * (cdf(lower_limit_c) + 1 - cdf(upper_limit_c))
        if len(overall_values) >= 3:
            sample = overall_values[:5000]
            result["normality_p_value"] = float(shapiro(sample).pvalue)
    elif len(overall_values) < 2:
        result["capability_status"] = "insufficient_data"
        result["capability_explanation"] = f"Not enough data for a reliable capability estimate (minimum {MIN_CAPABILITY_N} readings)."
    else:
        result["capability_status"] = "unsupported"
        result["capability_explanation"] = "Pp/Ppk are unsupported because the overall history has no measurable variation."
    if len(overall_values) < MIN_CAPABILITY_N:
        result["capability_status"] = "insufficient_data"
        result["capability_explanation"] = f"Not enough data for a reliable capability estimate (minimum {MIN_CAPABILITY_N} readings)."
        result["pp"] = None
        result["ppk"] = None
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
    if freshness < 0 or freshness > stale_after_minutes:
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
        "as_of_utc": None,
        "warnings": [],
    }
    if valid:
        result["as_of_utc"] = valid[-1]["timestamp"].isoformat()
    if not valid:
        result["status"] = "unknown"
        result["warnings"].append(warning("FORECAST_NO_VALID_READINGS", "No valid current reading is available; no trend forecast is available."))
        return result

    latest = valid[-1]
    age_minutes = (reference_time - latest["timestamp"]).total_seconds() / 60
    if age_minutes < 0 or age_minutes > stale_after_minutes:
        result["status"] = "unknown"
        result["warnings"].append(warning("FORECAST_STALE_READINGS", "Recent temperature readings are stale; no trend forecast is available."))
        return result

    current = float(latest["temperature_c"])
    if current < lower_limit_c or current > upper_limit_c:
        result["status"] = "currently_out_of_range"
        return result
    if len(valid) < minimum_readings:
        result["warnings"].append(warning("FORECAST_INSUFFICIENT_READINGS", "Not enough recent valid readings to estimate a temperature trend.", "info"))
        return result

    span_minutes = (latest["timestamp"] - valid[0]["timestamp"]).total_seconds() / 60
    if span_minutes < minimum_span_minutes:
        result["warnings"].append(warning("FORECAST_SHORT_HISTORY", "Recent readings do not span enough time to estimate a temperature trend.", "info"))
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
    if slope_per_minute > 0:
        candidate = (upper_limit_c - current) / slope_per_minute
        if 0 <= candidate <= forecast_minutes:
            crossing_minutes = candidate
    elif slope_per_minute < 0:
        candidate = (lower_limit_c - current) / slope_per_minute
        if 0 <= candidate <= forecast_minutes:
            crossing_minutes = candidate

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


def classify_temperature_warning(
    summary: dict[str, Any],
    forecast: dict[str, Any],
    active_control_signals: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply the supervisor warning priority to one refrigerator's current state."""
    if summary["state"] == "unknown":
        reason = (
            "No valid current temperature reading is available."
            if summary["latest_timestamp_utc"] is None
            else "The latest temperature reading is stale."
        )
        return {
            "status": "unknown",
            "label": "Current condition unknown",
            "reason": reason,
            "warning_active": True,
        }
    if summary["state"] in {"below_limit", "above_limit"}:
        return {
            "status": "currently_out_of_range",
            "label": "Currently outside limits",
            "reason": "The latest temperature reading is outside the configured storage limits.",
            "warning_active": True,
        }
    if forecast["status"] == "approaching_limit":
        crossing_minutes = max(0, round(forecast["predicted_minutes_to_limit"] or 0))
        return {
            "status": "approaching_limit",
            "label": f"Limit may be reached in {crossing_minutes} minutes",
            "reason": "The preceding two hours of valid readings project a storage-limit crossing within 60 minutes.",
            "warning_active": True,
        }
    if active_control_signals:
        rules = "; ".join(dict.fromkeys(signal["rule"] for signal in active_control_signals))
        return {
            "status": "unusual_pattern",
            "label": "Unusual temperature pattern",
            "reason": f"Control-chart rule triggered at the latest valid reading: {rules}.",
            "warning_active": True,
        }
    if forecast["status"] == "insufficient_data":
        reason = "Temperature is within limits; insufficient history for a forecast."
    else:
        reason = "Temperature is within limits; the 60-minute estimate does not cross a storage limit."
    return {
        "status": "within_limits",
        "label": "Within limits",
        "reason": reason,
        "warning_active": False,
    }
