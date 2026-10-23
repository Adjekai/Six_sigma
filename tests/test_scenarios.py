import json

import pytest

from bloodwatch.repository import load_data
from bloodwatch.service import build_dashboard


def test_three_related_datasets_are_valid():
    data = load_data()
    assert {row["refrigerator_id"] for row in data["refrigerator_periods"]} == {"R1", "R2", "R3"}
    assert {row["generator_id"] for row in data["refrigerator_periods"]} == {"G1"}
    assert any(not row["mechanical_failure"] for row in data["refrigerator_periods"])
    assert any(row["normal_baseline"] for row in data["refrigerator_periods"])


def test_dashboard_returns_strict_json():
    result = build_dashboard()
    json.dumps(result, allow_nan=False)
    assert result["dataset"]["synthetic"] is True
    assert result["conditions"]["temperature_series"]


def test_mechanical_rate_uses_failures_and_all_operating_periods():
    data = load_data()
    expected_failures = sum(row["mechanical_failure"] for row in data["refrigerator_periods"])
    expected_hours = sum(row["observed_operating_hours"] for row in data["refrigerator_periods"])
    reliability = build_dashboard()["reliability"]["refrigerators"][0]
    assert reliability["failures"] == expected_failures == 2
    assert reliability["exposure_hours"] == expected_hours == 49_366
    assert reliability["rate_per_hour"] == pytest.approx(2 / 49_366)


def test_generator_denominator_includes_successes_but_not_unknowns():
    generator = build_dashboard()["reliability"]["generators"][0]
    assert generator["failed_demands"] == 2
    assert generator["successful_demands"] == 18
    assert generator["known_demands"] == 20
    assert generator["unknown_demands"] == 1
    assert generator["failed_start_probability"] == pytest.approx(0.10)


def test_blackout_is_one_generator_demand_but_three_cooling_histories():
    result = build_dashboard()
    current = [
        row for row in result["reliability"]["breach_recovery"]["incidents"]
        if row["failure_event_id"] == "GF-020"
    ]
    assert len(current) == 3
    assert result["reliability"]["refrigerators"][0]["failures"] == 2


def test_every_cooling_interruption_has_matching_temperature_readings():
    recovery = build_dashboard()["reliability"]["breach_recovery"]
    assert recovery["unknown_count"] == 0
    assert all(row["breach_status"] != "unknown" for row in recovery["incidents"])


def test_unknown_refrigerator_is_rejected():
    with pytest.raises(ValueError, match="Unknown refrigerator"):
        build_dashboard(refrigerator_id="DOES-NOT-EXIST")


def test_stable_scenario_has_no_crossings_or_failed_generator_starts():
    result = build_dashboard(scenario="stable")
    assert result["scenario"]["synthetic_data"] is True
    assert result["scenario"]["observed_alarm"] is None
    assert result["reliability"]["selected_generator"]["failed_demands"] == 0
    assert result["reliability"]["selected_breach_recovery"]["breached_count"] == 0
    assert all(row["status"] == "within_limits" for row in result["conditions"]["equipment"])


def test_degrading_refrigerator_scenario_flags_breach_and_inventory_value():
    result = build_dashboard(scenario="degrading_refrigerator")
    alarm = result["scenario"]["observed_alarm"]
    refrigerator = next(row for row in result["conditions"]["equipment"] if row["equipment_id"] == "R1")
    assert alarm["status"] == "review_required"
    assert alarm["refrigerator_id"] == "R1"
    assert alarm["affected_inventory_value_usd"] == 400 * 240
    assert alarm["excursion_duration_hours"] > 0
    assert refrigerator["status"] == "review_required"
    warning = next(row for row in result["conditions"]["risk_forecasts"] if row["refrigerator_id"] == "R1")
    assert warning["status"] == "observed_replay_breach"
    assert warning["warning_label"] == "Observed breach in replay"
    assert "latest replay reading shows recovery" in warning["decision_support_reason"]
    assert result["conditions"]["temperature_warning_count"] == 1


def test_blackout_scenario_adds_one_failed_start_and_three_cooling_events():
    result = build_dashboard(scenario="blackout_failed_generator")
    event_rows = [
        row for row in result["reliability"]["breach_recovery"]["incidents"]
        if row["failure_event_id"] == "SIM-GF-001"
    ]
    assert result["scenario"]["observed_alarm"]["cause"] == "generator_failed_start"
    assert result["reliability"]["selected_generator"]["failed_demands"] == 3
    assert len(event_rows) == 3
    assert all(row["breach_status"] == "breached" for row in event_rows)
    alarm = result["scenario"]["observed_alarm"]
    assert alarm["outage_duration_hours"] == 1
    assert alarm["recovery_hours"] is not None
    warnings = result["conditions"]["risk_forecasts"]
    assert all(row["status"] == "observed_replay_breach" for row in warnings)
    assert result["conditions"]["temperature_warning_count"] == 3


def test_live_temperature_does_not_change_csv_baseline_or_reliability(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from bloodwatch.live_data import record_temperature_reading

    monkeypatch.setenv("BLOODWATCH_LIVE_DB", str(tmp_path / "live.sqlite3"))
    baseline = build_dashboard()
    record_temperature_reading("R1", datetime(2026, 10, 21, 12, tzinfo=timezone.utc), 5.9, True, "test")
    live = build_dashboard()
    assert live["conditions"]["process_analysis"]["center_line_c"] == baseline["conditions"]["process_analysis"]["center_line_c"]
    assert live["conditions"]["process_analysis"]["upper_control_limit_c"] == baseline["conditions"]["process_analysis"]["upper_control_limit_c"]
    assert live["reliability"]["refrigerators"][0]["failures"] == baseline["reliability"]["refrigerators"][0]["failures"] == 2
    assert live["reliability"]["refrigerators"][0]["exposure_hours"] == baseline["reliability"]["refrigerators"][0]["exposure_hours"] == 49_366


def test_scenario_switch_returns_distinct_reference_and_alarm_data():
    stable = build_dashboard(scenario="stable")
    degrading = build_dashboard(scenario="degrading_refrigerator")
    blackout = build_dashboard(scenario="blackout_failed_generator")
    assert stable["scenario"]["id"] == "stable" and stable["scenario"]["observed_alarm"] is None
    assert degrading["scenario"]["observed_alarm"]["excursion_duration_hours"] is not None
    assert blackout["scenario"]["observed_alarm"]["cause"] == "generator_failed_start"
