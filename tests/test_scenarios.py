import json

import pytest

from bloodwatch.repository import available_scenarios, load_scenario
from bloodwatch.service import build_dashboard


EXPECTED_SCENARIOS = {"normal", "refrigerator_breakdown", "blackout_failed_backup"}


def test_all_scenarios_are_available_and_valid():
    assert {row["id"] for row in available_scenarios()} == EXPECTED_SCENARIOS
    for scenario_id in EXPECTED_SCENARIOS:
        load_scenario(scenario_id)


@pytest.mark.parametrize("scenario_id", sorted(EXPECTED_SCENARIOS))
def test_every_scenario_returns_strict_json(scenario_id):
    result = build_dashboard(scenario_id)
    json.dumps(result, allow_nan=False)
    assert result["scenario"]["synthetic"] is True
    assert result["conditions"]["temperature_series"]


def test_breakdown_has_known_mechanical_rate_and_loss():
    result = build_dashboard("refrigerator_breakdown", horizon_operating_days=1_000 / 24)
    reliability = result["reliability"]["refrigerators"][0]
    assert reliability["failures"] == 2
    assert reliability["exposure_hours"] == 20_000
    assert reliability["failure_probability"] == pytest.approx(0.09516258196404048)
    assert result["financial"]["actual_historical_loss_usd"] == 7_500


def test_blackout_counts_one_demand_not_one_per_refrigerator():
    result = build_dashboard("blackout_failed_backup")
    generator = result["reliability"]["generators"][0]
    assert generator["failed_demands"] == 2
    assert generator["known_demands"] == 20
    assert generator["failed_start_probability"] == pytest.approx(0.10)
    assert len(result["reliability"]["breach_recovery"]["incidents"]) == 3


def test_unknown_refrigerator_is_rejected():
    with pytest.raises(ValueError, match="Unknown refrigerator"):
        build_dashboard("normal", refrigerator_id="DOES-NOT-EXIST")
