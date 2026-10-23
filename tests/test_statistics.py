import math
from datetime import datetime, timedelta, timezone

import pytest

from bloodwatch.financial import expected_annual_blackout_loss, expected_inventory_loss
from bloodwatch.incidents import summarize_breach_and_recovery
from bloodwatch.reliability import generator_reliability, refrigerator_reliability
from bloodwatch.temperature import (
    analyze_temperature_process,
    classify_temperature_warning,
    forecast_temperature_limit_crossing,
    summarize_temperature,
)
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


def test_reliability_time_terminated_intervals_match_known_answer():
    result = refrigerator_reliability(2, 49_366, 720)
    assert result["rate_interval_95"]["lower"] == pytest.approx(4.9e-6, rel=.02)
    assert result["rate_interval_95"]["upper"] == pytest.approx(1.46e-4, rel=.01)
    assert result["mtbf_interval_95"]["lower"] == pytest.approx(6_800, rel=.02)
    assert result["mtbf_interval_95"]["upper"] == pytest.approx(203_800, rel=.01)
    assert result["failure_probability_interval_95"]["lower"] == pytest.approx(.0035, abs=.0002)
    assert result["failure_probability_interval_95"]["upper"] == pytest.approx(.10, abs=.001)


def test_zero_failures_retains_uncertainty():
    result = refrigerator_reliability(0, 10_000, 1_000)
    assert result["rate_per_hour"] == 0
    assert result["mtbf_hours"] is None
    assert result["rate_interval_95"]["upper"] > 0
    assert result["warnings"][0]["code"] == "ZERO_FAILURES"
    assert result["rate_interval_95"]["upper"] == pytest.approx(2.996 / 10_000)


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
    assert expected_inventory_loss(1 - math.exp(-(2 / 49_366) * 720), 96_000) == pytest.approx(2760, rel=.01)
    assert .10 * 252_000 == 25_200
    assert .30103365 * 252_000 == pytest.approx(75_860, abs=1)


def test_control_chart_uses_moving_range_estimator_and_run_rules():
    baseline = [reading(i * 15, 3.8 + (i % 2) * .1) for i in range(20)]
    displayed = [reading(i * 15, 4.5 + i * .05) for i in range(8)]
    result = analyze_temperature_process(displayed, baseline, baseline + displayed)
    assert result["within_sigma_c"] == pytest.approx(result["moving_range_average_c"] / 1.128)
    assert result["lower_control_limit_c"] == pytest.approx(result["center_line_c"] - 2.66 * result["moving_range_average_c"])
    assert result["moving_range_ucl_c"] == pytest.approx(3.267 * result["moving_range_average_c"])
    rules = {signal["rule"] for signal in result["control_signals"]}
    assert "8 consecutive points on one side" in rules
    assert "6 consecutive points steadily increasing or decreasing" in rules
    assert "3-sigma control limit" in rules
    assert all(signal["points"] for signal in result["control_signals"])
    assert all(signal["start_timestamp_utc"] <= signal["timestamp_utc"] for signal in result["control_signals"])
    assert all(signal["points"][-1]["timestamp_utc"] == signal["timestamp_utc"] for signal in result["control_signals"])
    eight_point_signal = next(signal for signal in result["control_signals"] if signal["rule"] == "8 consecutive points on one side")
    assert len(eight_point_signal["points"]) == 8
    assert [point["temperature_c"] for point in eight_point_signal["points"]] == [row["temperature_c"] for row in displayed]

    decreasing = [reading(i * 15, 5.5 - i * .05) for i in range(6)]
    decreasing_result = analyze_temperature_process(decreasing, baseline, baseline + decreasing)
    assert any(
        signal["rule"] == "6 consecutive points steadily increasing or decreasing"
        for signal in decreasing_result["control_signals"]
    )


def test_invalid_reading_breaks_consecutive_control_chart_runs():
    baseline = [reading(i * 15, 3.8 + (i % 2) * .1) for i in range(20)]
    displayed = [reading(400 + i * 15, 4.2 + i * .1) for i in range(4)]
    displayed.append(reading(460, None, valid=False))
    displayed.extend(reading(475 + i * 15, 4.6 + i * .1) for i in range(4))
    result = analyze_temperature_process(displayed, baseline, baseline + displayed)
    rules = {signal["rule"] for signal in result["control_signals"]}
    assert "8 consecutive points on one side" not in rules
    assert "6 consecutive points steadily increasing or decreasing" not in rules


def test_capability_requires_minimum_sample_and_excludes_invalid_values():
    baseline = [reading(i * 15, 4 + (i % 2) * .1) for i in range(20)]
    overall = [reading(i * 15, 6.2 if i < 2 else 4.1 + (i % 5) * .05) for i in range(20)] + [reading(400, 99, valid=False)]
    result = analyze_temperature_process(overall, baseline, overall)
    assert result["capability_status"] == "insufficient_data"
    assert result["overall_count"] == 20
    assert result["ppk"] is None
    assert result["observed_out_of_spec_percent"] == 10
    assert result["normal_theory_out_of_spec_percent"] is not None


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


def test_temperature_forecast_flags_limit_crossing():
    reference = datetime(2026, 1, 1, 0, 45, tzinfo=UTC)
    rows = [reading(minutes, temperature) for minutes, temperature in ((0, 4.0), (15, 4.5), (30, 5.0), (45, 5.5))]
    result = forecast_temperature_limit_crossing(rows, reference)
    assert result["status"] == "approaching_limit"
    assert result["predicted_minutes_to_limit"] == pytest.approx(15)
    assert result["projected_temperature_c"] == pytest.approx(7.5)
    assert result["slope_c_per_hour"] == pytest.approx(2)
    assert result["as_of_utc"] == rows[-1]["timestamp"].isoformat()


def test_temperature_forecast_includes_crossing_at_60_minute_boundary():
    reference = datetime(2026, 1, 1, 1, 30, tzinfo=UTC)
    rows = [reading(minutes, temperature) for minutes, temperature in ((0, 4.75), (30, 5.0), (60, 5.25), (90, 5.5))]
    result = forecast_temperature_limit_crossing(rows, reference)
    assert result["status"] == "approaching_limit"
    assert result["predicted_minutes_to_limit"] == pytest.approx(60)


def test_temperature_forecast_requires_fresh_sufficient_data():
    reference = datetime(2026, 1, 1, 2, 0, tzinfo=UTC)
    rows = [reading(minutes, 4.0) for minutes in (0, 15, 30, 45)]
    assert forecast_temperature_limit_crossing(rows, reference)["status"] == "unknown"
    assert forecast_temperature_limit_crossing(rows[:3], rows[2]["timestamp"])["status"] == "insufficient_data"


def test_immediate_breach_detection_does_not_require_forecast_history():
    row = reading(0, 6.2)
    result = forecast_temperature_limit_crossing([row], row["timestamp"])
    assert result["status"] == "currently_out_of_range"
    assert result["reading_count"] == 1
    assert result["projected_temperature_c"] is None


def test_warning_priority_statuses_reasons_and_recovery():
    baseline = [reading(index * 15, 3.96 + (index % 2) * .08) for index in range(20)]
    warning_status_cases = (
        ("Normal", (4.0, 4.1, 3.9, 4.0)),
        ("Warming", (4.0, 4.1, 4.2, 4.3)),
        ("Projected crossing", (4.0, 4.4, 4.9, 5.4)),
        ("Actual breach", (4.0, 4.8, 5.6, 6.3)),
        ("Recovery", (4.0, 4.1, 3.9, 4.0)),
    )
    expected = {
        "Normal": "within_limits",
        "Warming": "unusual_pattern",
        "Projected crossing": "approaching_limit",
        "Actual breach": "currently_out_of_range",
        "Recovery": "within_limits",
    }
    results = {}
    for stage, values in warning_status_cases:
        rows = [reading(offset, value) for offset, value in zip((0, 30, 60, 90), values)]
        reference = rows[-1]["timestamp"]
        summary = summarize_temperature(rows, reference)
        forecast = forecast_temperature_limit_crossing(rows, reference)
        process = analyze_temperature_process(rows, baseline, rows)
        active = [signal for signal in process["control_signals"] if signal["index"] == len(rows) - 1]
        results[stage] = classify_temperature_warning(summary, forecast, active)
        assert results[stage]["status"] == expected[stage]

    assert results["Projected crossing"]["label"].startswith("Limit may be reached in ")
    assert results["Actual breach"]["label"] == "Currently outside limits"
    assert results["Recovery"]["label"] == "Within limits"
    assert sum(result["warning_active"] for result in results.values()) == 3


def test_warning_unknown_insufficient_history_and_control_rule_clear():
    reference = datetime(2026, 1, 1, 1, tzinfo=UTC)
    missing = summarize_temperature([], reference)
    no_forecast = forecast_temperature_limit_crossing([], reference)
    unknown = classify_temperature_warning(missing, no_forecast, [])
    assert unknown == {
        "status": "unknown",
        "label": "Current condition unknown",
        "reason": "No valid current temperature reading is available.",
        "warning_active": True,
    }

    current_row = reading(60, 4.0)
    current = summarize_temperature([current_row], reference)
    insufficient = forecast_temperature_limit_crossing([current_row], reference)
    within = classify_temperature_warning(current, insufficient, [])
    assert within["status"] == "within_limits"
    assert within["reason"] == "Temperature is within limits; insufficient history for a forecast."

    signal = {"index": 0, "value_c": 4.0, "rule": "3-sigma control limit"}
    unusual = classify_temperature_warning(current, insufficient, [signal])
    assert unusual["status"] == "unusual_pattern"
    assert "3-sigma control limit" in unusual["reason"]
    assert classify_temperature_warning(current, insufficient, [])["warning_active"] is False


def test_stale_out_of_range_reading_is_unknown_before_breach():
    row = reading(0, 6.4)
    reference = row["timestamp"] + timedelta(minutes=31)
    summary = summarize_temperature([row], reference)
    forecast = forecast_temperature_limit_crossing([row], reference)
    result = classify_temperature_warning(summary, forecast, [])
    assert result["status"] == "unknown"
    assert result["label"] == "Current condition unknown"


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
    assert result["incidents"][0]["stayed_in_range_at_least_minutes"] == pytest.approx(30)
    assert result["censored_minimum_minutes"] == pytest.approx(30)


def test_initial_breach_is_zero_with_warning():
    result = summarize_breach_and_recovery([incident()], [reading(0, 6.2)])
    assert result["incidents"][0]["observed_hours_to_breach_or_censoring"] == 0
    assert any(item["code"] == "INITIALLY_BREACHED" for item in result["warnings"])
