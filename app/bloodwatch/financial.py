from __future__ import annotations

from statistics import mean
from typing import Any

from .common import warning


def expected_inventory_loss(failure_probability: float | None, inventory_value_usd: float | None) -> float | None:
    if failure_probability is None or inventory_value_usd is None:
        return None
    if not 0 <= failure_probability <= 1 or inventory_value_usd < 0:
        raise ValueError("Expected-loss inputs must be a probability and nonnegative inventory value")
    return failure_probability * inventory_value_usd


def expected_annual_blackout_loss(
    blackouts_per_year: float,
    failed_start_probability: float | None,
    loss_probability_given_failed_start: float | None,
    mean_loss_given_loss_usd: float | None,
) -> float | None:
    factors = (blackouts_per_year, failed_start_probability, loss_probability_given_failed_start, mean_loss_given_loss_usd)
    if any(value is None for value in factors):
        return None
    if any(value < 0 for value in factors):
        raise ValueError("Expected-loss factors must be nonnegative")
    return blackouts_per_year * failed_start_probability * loss_probability_given_failed_start * mean_loss_given_loss_usd


def summarize_financials(
    equipment: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    blackouts: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
    affected_refrigerators: set[str],
    mechanical_rate_per_hour: float | None,
    annual_operating_hours: float = 8760,
) -> dict[str, Any]:
    warnings = []
    incident_by_id = {row["incident_id"]: row for row in incidents}
    current_rows = [row for row in inventory if row["record_type"] == "current_snapshot" and row["refrigerator_id"] in affected_refrigerators]
    exposed_by_lot: dict[str, float] = {}
    for row in current_rows:
        if row["value_per_bag_usd"] is None:
            warnings.append(warning("UNKNOWN_CURRENT_VALUE", f"Current value is unknown for lot {row['lot_id']}."))
            continue
        exposed_by_lot[row["lot_id"]] = row["bags_present"] * row["value_per_bag_usd"]
    inventory_exposed = sum(exposed_by_lot.values())

    outcomes = [row for row in inventory if row["record_type"] == "incident_outcome"]
    actual_loss = 0.0
    loss_by_cause: dict[str, float] = {}
    known_incident_losses: dict[str, float] = {}
    for row in outcomes:
        if row["bags_written_off"] is None or row["value_per_bag_usd"] is None:
            warnings.append(warning("UNKNOWN_INCIDENT_OUTCOME", f"Loss is unknown for lot {row['lot_id']}."))
            continue
        loss = row["bags_written_off"] * row["value_per_bag_usd"]
        actual_loss += loss
        known_incident_losses[row["incident_id"]] = known_incident_losses.get(row["incident_id"], 0.0) + loss
        cause = incident_by_id.get(row["incident_id"], {}).get("cause", "unknown")
        pathway = "mechanical" if cause == "mechanical" else "blackout"
        loss_by_cause[pathway] = loss_by_cause.get(pathway, 0.0) + loss

    completed_mechanical = [row for row in incidents if row["cause"] == "mechanical" and row["cooling_restored"]]
    mechanical_losses = [known_incident_losses[row["incident_id"]] for row in completed_mechanical if row["incident_id"] in known_incident_losses]
    expected_mechanical = None
    if mechanical_rate_per_hour is not None and mechanical_losses:
        expected_mechanical = mechanical_rate_per_hour * annual_operating_hours * mean(mechanical_losses)
        if all(loss == 0 for loss in mechanical_losses):
            warnings.append(warning("NO_OBSERVED_MECHANICAL_LOSS", "No completed mechanical incident had a recorded loss; future loss is not proven to be zero.", "info"))

    observation_starts = [row["observation_start"] for row in equipment]
    observation_ends = [row["observation_end"] for row in equipment]
    site_years = ((max(observation_ends) - min(observation_starts)).total_seconds() / (365.25 * 24 * 3600)) if equipment else 0
    blackouts_per_year = len(blackouts) / site_years if site_years > 0 else None
    known_demands = [row for row in blackouts if row["auto_start_outcome"] in {"success", "failure"}]
    failed = [row for row in known_demands if row["auto_start_outcome"] == "failure"]
    failed_probability = len(failed) / len(known_demands) if known_demands else None

    blackout_incidents: dict[str, list[str]] = {}
    for incident in incidents:
        if incident["blackout_id"]:
            blackout_incidents.setdefault(incident["blackout_id"], []).append(incident["incident_id"])
    failed_losses = []
    for blackout in failed:
        related = blackout_incidents.get(blackout["blackout_id"], [])
        if related and all(incident_id in known_incident_losses for incident_id in related):
            failed_losses.append(sum(known_incident_losses[incident_id] for incident_id in related))
    probability_loss = (sum(loss > 0 for loss in failed_losses) / len(failed_losses)) if failed_losses else None
    positive_losses = [loss for loss in failed_losses if loss > 0]
    mean_positive_loss = mean(positive_losses) if positive_losses else None
    if len(failed_losses) < len(failed):
        warnings.append(warning("INCOMPLETE_BLACKOUT_OUTCOMES", f"{len(failed) - len(failed_losses)} failed blackout demand(s) lack complete loss outcomes."))

    expected_blackout = expected_annual_blackout_loss(
        blackouts_per_year or 0,
        failed_probability,
        probability_loss,
        mean_positive_loss,
    ) if blackouts_per_year is not None else None

    return {
        "actual_historical_loss_usd": actual_loss,
        "inventory_exposed_usd": inventory_exposed,
        "expected_annual_mechanical_loss_usd": expected_mechanical,
        "expected_annual_blackout_loss_usd": expected_blackout,
        "annual_operating_hours_assumption": annual_operating_hours,
        "blackouts_per_year": blackouts_per_year,
        "blackout_factors": {
            "failed_start_probability": failed_probability,
            "loss_probability_given_failed_start": probability_loss,
            "mean_loss_given_loss_usd": mean_positive_loss,
            "failed_blackouts_with_known_loss_outcomes": len(failed_losses),
        },
        "loss_by_cause": [{"cause": cause, "loss_usd": value} for cause, value in sorted(loss_by_cause.items())],
        "warnings": warnings,
    }
