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
    result = build_dashboard('blackout_failed_backup', refrigerator_id='R-O3')
    selected = result['reliability']['selected_breach_recovery']
    assert len(selected['incidents']) == 1
    assert selected['incidents'][0]['refrigerator_id'] == 'R-O3'
    assert selected['breached_count'] == 0
    assert selected['mean_observed_hours_to_breach_breached_only'] is None
    assert result['reliability']['selected_generator']['generator_id'] == 'G-W'


def test_breach_time_is_observed_storage_crossing_not_blood_viability():
    result = build_dashboard('refrigerator_breakdown', refrigerator_id='R-B1')
    selected = result['reliability']['selected_breach_recovery']
    assert selected['mean_observed_hours_to_breach_breached_only'] == 1.25
    record = selected['incidents'][0]
    assert record['cooling_loss_utc'] == '2026-10-20T08:00:00+00:00'
    assert record['first_breach_utc'] == '2026-10-20T09:15:00+00:00'
    assert record['cooling_restored_utc'] == '2026-10-20T10:00:00+00:00'
    assert result['reliability']['selected_refrigerator_model']['equipment_count'] == 3
