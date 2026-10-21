import math
from datetime import datetime, timedelta, timezone

import pytest

from bloodwatch.financial import expected_annual_blackout_loss
from bloodwatch.incidents import summarize_breach_and_recovery
from bloodwatch.reliability import generator_reliability, refrigerator_reliability
from bloodwatch.temperature import summarize_temperature


UTC = timezone.utc


def reading(minutes, temperature, valid=True):
    return {
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minutes),
        "refrigerator_id": "R-1",
        "temperature_c": temperature,
        "reading_valid": valid,
    }


def incident(restored_minutes=60, observation_minutes=120):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return {
        "incident_id": "I-1",
        "refrigerator_id": "R-1",
        "cause": "mechanical",
        "cooling_loss": start,
        "observation_end": start + timedelta(minutes=observation_minutes),
        "cooling_restored": None if restored_minutes is None else start + timedelta(minutes=restored_minutes),
        "blackout_id": None,
    }


def test_refrigerator_known_answer():
    result = refrigerator_reliability(2, 20_000, 1_000)
    assert result["rate_per_hour"] == pytest.approx(0.0001)
    assert result["mtbf_hours"] == pytest.approx(10_000)
    assert result["failure_probability"] == pytest.approx(0.09516258196404048)
    probabilities = [point["failure_probability"] for point in result["cdf"]]
    assert probabilities == sorted(probabilities)


def test_zero_failures_retains_uncertainty():
    result = refrigerator_reliability(0, 10_000, 1_000)
    assert result["rate_per_hour"] == 0
    assert result["mtbf_hours"] is None
    assert result["rate_interval_95"]["upper"] > 0
    assert result["warnings"][0]["code"] == "ZERO_FAILURES"


def test_zero_exposure_is_insufficient():
    result = refrigerator_reliability(0, 0, 1_000)
    assert result["status"] == "insufficient_data"
    assert result["failure_probability"] is None


def test_generator_known_answer_and_wilson_interval():
    result = generator_reliability(2, 18)
    assert result["failed_start_probability"] == pytest.approx(0.10)
    assert result["wilson_interval_95"]["lower"] == pytest.approx(0.02786648)
    assert result["wilson_interval_95"]["upper"] == pytest.approx(0.30103365)
    assert result["cumulative_failure"][-1]["failure_probability"] == pytest.approx(1 - 0.9**5)


def test_no_generator_demands_is_insufficient():
    assert generator_reliability(0, 0)["status"] == "insufficient_data"


def test_financial_hand_check():
    assert expected_annual_blackout_loss(4, 0.10, 0.25, 20_000) == pytest.approx(2_000)


def test_exact_temperature_boundaries_are_in_range():
    reference = datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
    lower = summarize_temperature([reading(0, 1.0)], reference)
    upper = summarize_temperature([reading(0, 6.0)], reference)
    assert lower["state"] == "within_limits"
    assert upper["state"] == "within_limits"


def test_missing_temperature_is_unknown_not_zero():
    reference = datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
    result = summarize_temperature([reading(0, None, valid=False)], reference)
    assert result["state"] == "unknown"
    assert result["latest_temperature_c"] is None


def test_breach_detection_and_recovery_are_distinct():
    result = summarize_breach_and_recovery(
        [incident(restored_minutes=60)],
        [reading(0, 4.0), reading(30, 6.2), reading(60, 5.0)],
    )
    assert result["breached_count"] == 1
    assert result["mean_observed_hours_to_breach_breached_only"] == pytest.approx(0.5)
    assert result["mean_recovery_hours"] == pytest.approx(1.0)


def test_no_breach_before_recovery_is_censored():
    result = summarize_breach_and_recovery(
        [incident(restored_minutes=30)],
        [reading(0, 4.0), reading(30, 5.5), reading(60, 7.0)],
    )
    assert result["unbreached_censored_count"] == 1
    assert result["mean_observed_hours_to_breach_breached_only"] is None


def test_initial_breach_is_zero_with_warning():
    result = summarize_breach_and_recovery([incident()], [reading(0, 6.2)])
    assert result["incidents"][0]["observed_hours_to_breach_or_censoring"] == 0
    assert any(item["code"] == "INITIALLY_BREACHED" for item in result["warnings"])
