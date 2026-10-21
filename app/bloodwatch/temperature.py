from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any

from .common import warning


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
