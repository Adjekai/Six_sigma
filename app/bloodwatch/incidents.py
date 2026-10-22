from __future__ import annotations

from statistics import mean, median
from typing import Any

from .common import warning


def summarize_breach_and_recovery(
    incidents: list[dict[str, Any]],
    temperatures: list[dict[str, Any]],
    lower_limit_c: float = 1.0,
    upper_limit_c: float = 6.0,
) -> dict[str, Any]:
    per_incident = []
    breached_times = []
    recovery_hours = []
    warnings = []

    for incident in incidents:
        end = min(
            incident["observation_end"],
            incident["cooling_restored"] or incident["observation_end"],
        )
        readings = sorted(
            (
                row for row in temperatures
                if row["refrigerator_id"] == incident["refrigerator_id"]
                and row["reading_valid"]
                and row["temperature_c"] is not None
                and incident["cooling_loss"] <= row["timestamp"] <= end
                and row.get("related_failure_event_id") == incident.get("failure_event_id")
            ),
            key=lambda row: row["timestamp"],
        )
        breach = next(
            (row for row in readings if row["temperature_c"] < lower_limit_c or row["temperature_c"] > upper_limit_c),
            None,
        )
        if breach:
            elapsed = (breach["timestamp"] - incident["cooling_loss"]).total_seconds() / 3600
            status = "breached"
            breached_times.append(elapsed)
            if elapsed == 0:
                warnings.append(warning("INITIALLY_BREACHED", f"{incident['incident_id']} was already outside limits at its first observation."))
        elif readings:
            elapsed = (end - incident["cooling_loss"]).total_seconds() / 3600
            status = "unbreached_censored"
        else:
            elapsed = None
            status = "unknown"
            warnings.append(warning("MISSING_INCIDENT_TEMPERATURE", f"{incident['incident_id']} has no valid readings during its observed cooling-loss window."))

        recovery = None
        if incident["cooling_restored"]:
            recovery = (incident["cooling_restored"] - incident["cooling_loss"]).total_seconds() / 3600
            recovery_hours.append(recovery)
        per_incident.append(
            {
                "incident_id": incident["incident_id"],
                "failure_event_id": incident.get("failure_event_id"),
                "refrigerator_id": incident["refrigerator_id"],
                "cause": incident["cause"],
                "cooling_loss_utc": incident["cooling_loss"].isoformat(),
                "first_breach_utc": breach["timestamp"].isoformat() if breach else None,
                "cooling_restored_utc": incident["cooling_restored"].isoformat() if incident["cooling_restored"] else None,
                "breach_status": status,
                "observed_hours_to_breach_or_censoring": elapsed,
                "recovery_hours": recovery,
            }
        )

    return {
        "incidents": per_incident,
        "breached_count": sum(row["breach_status"] == "breached" for row in per_incident),
        "unbreached_censored_count": sum(row["breach_status"] == "unbreached_censored" for row in per_incident),
        "unknown_count": sum(row["breach_status"] == "unknown" for row in per_incident),
        "mean_observed_hours_to_breach_breached_only": mean(breached_times) if breached_times else None,
        "completed_recovery_count": len(recovery_hours),
        "mean_recovery_hours": mean(recovery_hours) if recovery_hours else None,
        "median_recovery_hours": median(recovery_hours) if recovery_hours else None,
        "unresolved_incident_count": sum(row["recovery_hours"] is None for row in per_incident),
        "warnings": warnings,
    }
