from datetime import datetime, timedelta, timezone

from bloodwatch.service import build_dashboard
from bloodwatch.temperature import summarize_temperature


def test_temperature_spread_matches_hand_calculation():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [dict(timestamp=start + timedelta(minutes=i), reading_valid=True, temperature_c=v)
            for i, v in enumerate([2., 4., 6.])]
    result = summarize_temperature(rows, start + timedelta(minutes=2))
    assert result['mean_c'] == 4
    assert result['minimum_c'] == 2
    assert result['maximum_c'] == 6
    assert result['standard_deviation_c'] == 2
    assert summarize_temperature(rows[:1], start)['standard_deviation_c'] is None


def test_selected_incidents_belong_to_selected_refrigerator():
    result = build_dashboard(refrigerator_id='R3')
    selected = result['reliability']['selected_breach_recovery']
    assert len(selected['incidents']) == 2
    assert all(row['refrigerator_id'] == 'R3' for row in selected['incidents'])
    assert selected['breached_count'] == 0
    assert selected['mean_observed_hours_to_breach_breached_only'] is None
    assert result['reliability']['selected_generator']['generator_id'] == 'G1'


def test_breach_time_is_observed_storage_crossing_not_blood_viability():
    result = build_dashboard(refrigerator_id='R1')
    selected = result['reliability']['selected_breach_recovery']
    record = next(row for row in selected['incidents'] if row['failure_event_id'] == 'RF-002')
    assert record['observed_hours_to_breach_or_censoring'] == 1.25
    assert record['cooling_loss_utc'] == '2026-10-19T16:00:00+00:00'
    assert record['first_breach_utc'] == '2026-10-19T17:15:00+00:00'
    assert record['cooling_restored_utc'] == '2026-10-19T18:00:00+00:00'
    most_recent = next(row for row in selected['incidents'] if row['failure_event_id'] == 'GF-020')
    assert selected['mean_observed_hours_to_breach_breached_only'] != most_recent['observed_hours_to_breach_or_censoring']
    assert result['reliability']['selected_refrigerator_model']['equipment_count'] == 3


def test_control_limits_do_not_change_with_display_window():
    short = build_dashboard(refrigerator_id='R1', temperature_window_hours=6)['conditions']['process_analysis']
    long = build_dashboard(refrigerator_id='R1', temperature_window_hours=24)['conditions']['process_analysis']
    assert short['baseline_source'] == 'documented_normal_operation'
    assert short['baseline_count'] == 672
    assert short['lower_control_limit_c'] == long['lower_control_limit_c']
    assert short['upper_control_limit_c'] == long['upper_control_limit_c']
    assert short['pp'] == long['pp']
    assert short['ppk'] == long['ppk']
