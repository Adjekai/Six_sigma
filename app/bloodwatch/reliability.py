from __future__ import annotations

import math
from typing import Any

from scipy.stats import chi2, norm

from .common import warning


def refrigerator_reliability(
    mechanical_failures: int,
    exposure_hours: float,
    horizon_hours: float,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    if mechanical_failures < 0 or int(mechanical_failures) != mechanical_failures:
        raise ValueError("mechanical_failures must be a nonnegative integer")
    if exposure_hours < 0 or horizon_hours < 0:
        raise ValueError("exposure_hours and horizon_hours must be nonnegative")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between zero and one")

    result: dict[str, Any] = {
        "status": "estimated",
        "failures": int(mechanical_failures),
        "exposure_hours": exposure_hours,
        "rate_per_hour": None,
        "rate_interval_95": {"lower": None, "upper": None},
        "mtbf_hours": None,
        "horizon_hours": horizon_hours,
        "reliability": None,
        "failure_probability": None,
        "cdf": [],
        "assumptions": ["Constant failure-occurrence rate", "Independent mechanical failure events", "Comparable pooled equipment"],
        "warnings": [],
    }
    if exposure_hours == 0:
        result["status"] = "insufficient_data"
        result["warnings"].append(warning("ZERO_EXPOSURE", "No mechanical operating exposure is available."))
        return result

    failures = int(mechanical_failures)
    alpha = 1 - confidence_level
    rate = failures / exposure_hours
    lower = 0.0 if failures == 0 else 0.5 * chi2.ppf(alpha / 2, 2 * failures) / exposure_hours
    upper = 0.5 * chi2.ppf(1 - alpha / 2, 2 * (failures + 1)) / exposure_hours
    result["rate_per_hour"] = rate
    result["rate_interval_95"] = {"lower": lower, "upper": upper}
    result["mtbf_hours"] = None if failures == 0 else 1 / rate
    result["reliability"] = math.exp(-rate * horizon_hours)
    result["failure_probability"] = 1 - result["reliability"]
    result["cdf"] = [
        {"operating_hours": horizon_hours * index / 10, "failure_probability": 1 - math.exp(-rate * horizon_hours * index / 10)}
        for index in range(11)
    ]
    if failures == 0:
        result["warnings"].append(
            warning("ZERO_FAILURES", "No failures were observed; this does not establish perfect reliability.", "info")
        )
    return result


def generator_reliability(
    failed_demands: int,
    successful_demands: int,
    unknown_demands: int = 0,
    confidence_level: float = 0.95,
    future_demands: int = 5,
) -> dict[str, Any]:
    if any(value < 0 or int(value) != value for value in (failed_demands, successful_demands, unknown_demands)):
        raise ValueError("Generator demand counts must be nonnegative integers")
    known = int(failed_demands + successful_demands)
    result: dict[str, Any] = {
        "status": "estimated",
        "failed_demands": int(failed_demands),
        "successful_demands": int(successful_demands),
        "known_demands": known,
        "unknown_demands": int(unknown_demands),
        "failed_start_probability": None,
        "wilson_interval_95": {"lower": None, "upper": None},
        "cumulative_failure": [],
        "assumptions": ["Comparable independent future blackout demands", "Recorded known outcomes are representative"],
        "warnings": [],
    }
    if known == 0:
        result["status"] = "insufficient_data"
        result["warnings"].append(warning("NO_KNOWN_DEMANDS", "No blackout demands have known start outcomes."))
        return result

    probability = failed_demands / known
    z = norm.ppf(0.5 + confidence_level / 2)
    denominator = 1 + z * z / known
    center = (probability + z * z / (2 * known)) / denominator
    half_width = z * math.sqrt((probability * (1 - probability) + z * z / (4 * known)) / known) / denominator
    result["failed_start_probability"] = probability
    result["wilson_interval_95"] = {"lower": max(0.0, center - half_width), "upper": min(1.0, center + half_width)}
    result["cumulative_failure"] = [
        {"future_demands": demand_count, "failure_probability": 1 - (1 - probability) ** demand_count}
        for demand_count in range(future_demands + 1)
    ]
    if unknown_demands:
        result["warnings"].append(warning("UNKNOWN_DEMAND_OUTCOMES", f"{unknown_demands} blackout outcomes are excluded from the denominator."))
    return result
