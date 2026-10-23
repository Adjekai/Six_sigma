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


def test_stable_demo_scenario_has_steady_temperature_and_no_observed_alarm():
    result = build_dashboard(scenario="stable")
    summary = result["conditions"]["temperature_summary"]
    assert result["scenario"]["synthetic_demo"] is True
    assert result["scenario"]["id"] == "stable"
    assert result["scenario"]["observed_alarm"] is None
    assert summary["minimum_c"] >= 1
    assert summary["maximum_c"] <= 6
    assert all(row["status"] == "within_limits" for row in result["conditions"]["equipment"])
    assert result["reliability"]["selected_generator"]["failed_demands"] == 0
    assert result["reliability"]["selected_breach_recovery"]["incidents"] == []
    assert all(row["incident_status"] == "none_active" for row in result["conditions"]["equipment"])


def test_degrading_refrigerator_demo_has_observed_excursion_and_inventory_value():
    result = build_dashboard(scenario="degrading_refrigerator")
    alarm = result["scenario"]["observed_alarm"]
    r1 = next(row for row in result["conditions"]["equipment"] if row["equipment_id"] == "R1")
    assert result["dataset"]["synthetic"] is True
    assert alarm["status"] == "review_required"
    assert alarm["refrigerator_id"] == "R1"
    assert alarm["excursion_duration_hours"] > 0
    assert alarm["recovery_hours"] == 3
    assert alarm["affected_inventory_value_usd"] == 400 * 240
    assert r1["status"] == "review_required"
    assert r1["incident_status"] == "none_active"
    assert result["reliability"]["selected_refrigerator_model"]["failures"] == 3


def test_blackout_demo_records_failed_start_observed_alarm_and_recovery():
    result = build_dashboard(scenario="blackout_failed_generator")
    alarm = result["scenario"]["observed_alarm"]
    generator = result["reliability"]["selected_generator"]
    event_rows = [row for row in result["reliability"]["breach_recovery"]["incidents"] if row["failure_event_id"] == "DEMO-GF-001"]
    assert generator["failed_demands"] == 3
    assert alarm["status"] == "review_required"
    assert alarm["cause"] == "generator_failed_start"
    assert alarm["recovery_hours"] == 4
    assert alarm["outage_duration_hours"] == 1
    assert alarm["first_breach_utc"] is not None
    assert len(event_rows) == 3
    assert all(row["breach_status"] == "breached" for row in event_rows)


def test_switching_demo_scenarios_returns_corresponding_data():
    from fastapi.testclient import TestClient

    from api import app

    client = TestClient(app)
    stable = client.get("/api/dashboard", params={"scenario": "stable"}).json()
    stable_repeat = client.get("/api/dashboard", params={"scenario": "stable"}).json()
    degrading = client.get("/api/dashboard", params={"scenario": "degrading_refrigerator"}).json()
    blackout = client.get("/api/dashboard", params={"scenario": "blackout_failed_generator"}).json()
    assert stable["scenario"]["id"] == "stable"
    assert stable == stable_repeat
    assert degrading["scenario"]["id"] == "degrading_refrigerator"
    assert degrading["scenario"]["observed_alarm"]["event_id"] == "DEMO-RF-001"
    assert blackout["scenario"]["id"] == "blackout_failed_generator"
    assert blackout["scenario"]["observed_alarm"]["event_id"] == "DEMO-GF-001"
    assert len({stable["conditions"]["temperature_series"][-1]["temperature_c"], degrading["conditions"]["temperature_series"][-1]["temperature_c"], blackout["conditions"]["temperature_series"][-1]["temperature_c"]}) > 1
