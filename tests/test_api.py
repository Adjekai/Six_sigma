from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from api import app
from bloodwatch.live_data import delete_simulated_temperature_readings, record_temperature_reading
from scripts.stream_temperature import WARNING_CYCLE


client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok", "service": "bloodwatch-api"}


def test_dashboard_frontend_is_served_without_a_build_step():
    response = client.get("/")
    assert response.status_code == 200
    assert "BloodWatch" in response.text
    assert "/app.js?v=unified-warnings-2" in response.text
    frontend = client.get("/app.js").text
    assert "loadDashboard" in frontend
    assert "About the datasets and live readings" in frontend
    assert "Live readings</strong> are sensor readings stored in the local database" in frontend
    assert "Rejected readings:" not in frontend
    assert "Data limitations" not in frontend
    assert "CSV history + incoming readings" in frontend
    assert "Synthetic demo scenarios" in frontend
    assert "state = { mode: 'live'" in frontend
    assert "Change analysis limits and estimate period" in frontend
    assert "Examples of product storage ranges" in frontend
    assert "Incoming-feed freshness uses current time" in frontend
    assert "Historical demonstration replay reference" in frontend
    assert "Scenario data as of" in frontend
    assert "row.reading_count" in frontend
    assert "row.slope_c_per_hour" in frontend
    assert "fullTimestamp(row.as_of_utc)" in frontend
    assert "What do the warnings mean?" in frontend
    assert "Temperature now → estimated in 60 minutes" in frontend
    assert "Inventory is stock recorded in the refrigerator, not confirmed loss" in frontend
    assert "preceding two hours of valid readings" in frontend
    assert "Refrigerator temperature history" in frontend
    assert "class=\"temperature-controls\"" in frontend
    assert "class=\"risk-row-info\"" in frontend
    assert "card('Overall temperature performance'" in frontend
    assert "card('Ppk / observed out-of-spec'" not in frontend
    assert "Refrigerator cooling failure" in frontend


def test_dashboard_uses_coherent_dataset():
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["selection"]["available_refrigerators"] == ["R1", "R2", "R3"]
    assert body["reliability"]["generators"][0]["known_demands"] == 20
    assert "scenario" not in body


def test_dashboard_exposes_temperature_risk_and_inventory_exposure():
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    forecasts = response.json()["conditions"]["risk_forecasts"]
    assert {row["refrigerator_id"] for row in forecasts} == {"R1", "R2", "R3"}
    assert all(row["forecast_minutes"] == 60 for row in forecasts)
    assert all(row["inventory_value_usd"] == row["inventory_bags"] * 240 for row in forecasts)
    assert all(row["status"] in {"within_limits", "approaching_limit", "currently_out_of_range", "unusual_pattern", "unknown"} for row in forecasts)
    assert all(row["warning_label"] for row in forecasts)
    assert all(row["decision_support_reason"] for row in forecasts)
    assert response.json()["conditions"]["temperature_warning_count"] == sum(row["warning_active"] for row in forecasts)
    reference_time = datetime.fromisoformat(response.json()["dataset"]["reference_time_utc"])
    forecast_times = [datetime.fromisoformat(row["as_of_utc"]) for row in forecasts]
    assert all(timestamp.tzinfo is not None and timestamp <= reference_time for timestamp in forecast_times)
    assert all(row["method"].startswith("Linear fit") for row in forecasts)
    assert all("reading_count" in row and "slope_c_per_hour" in row for row in forecasts)
    assert all("failure_probability" not in row["decision_support_reason"].lower() for row in forecasts)


def test_scenario_endpoint_lists_the_three_scenarios():
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [
        "stable",
        "degrading_refrigerator",
        "blackout_failed_generator",
    ]


def test_invalid_refrigerator_is_understandable():
    response = client.get("/api/dashboard", params={"refrigerator_id": "not-real"})
    assert response.status_code == 400
    assert "Unknown refrigerator" in response.json()["detail"]


def test_invalid_horizon_is_rejected():
    assert client.get("/api/dashboard", params={"horizon_operating_days": 0}).status_code == 422


def test_posted_live_reading_persists_and_updates_dashboard(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOODWATCH_LIVE_DB", str(tmp_path / "live.sqlite3"))
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "refrigerator_id": "R1",
        "timestamp_utc": timestamp,
        "temperature_c": 4.8,
        "reading_valid": True,
        "source": "test-sensor",
    }

    posted = client.post("/api/readings", json=payload)
    assert posted.status_code == 201
    assert posted.json()["status"] == "accepted"
    dashboard = client.get("/api/dashboard", params={"refrigerator_id": "R1"}).json()
    assert dashboard["dataset"]["live_reading_count"] == 1
    assert dashboard["conditions"]["temperature_summary"]["latest_temperature_c"] == 4.8
    assert dashboard["conditions"]["temperature_summary"]["latest_timestamp_utc"] == timestamp


def test_live_reading_rejects_unknown_refrigerator_and_naive_timestamp():
    payload = {
        "refrigerator_id": "R-UNKNOWN",
        "timestamp_utc": "2026-10-22T12:00:00",
        "temperature_c": 4.0,
    }
    assert client.post("/api/readings", json=payload).status_code == 422
    payload["timestamp_utc"] = "2026-10-22T12:00:00Z"
    assert client.post("/api/readings", json=payload).status_code == 400


def test_live_readings_reject_future_out_of_range_and_duplicate(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOODWATCH_LIVE_DB", str(tmp_path / "live.sqlite3"))
    payload = {"refrigerator_id": "R1", "timestamp_utc": "2026-10-21T12:00:00Z", "temperature_c": 4.1}
    assert client.post("/api/readings", json=payload).status_code == 201
    assert client.post("/api/readings", json=payload).status_code == 409
    payload["timestamp_utc"] = "2027-01-01T12:00:00Z"
    assert client.post("/api/readings", json=payload).status_code == 400
    payload["timestamp_utc"] = "2026-10-21T12:15:00Z"
    payload["temperature_c"] = 100
    assert client.post("/api/readings", json=payload).status_code == 422
    body = client.get("/api/dashboard").json()
    assert body["dataset"]["live_reading_count"] == 1
    assert body["dataset"]["rejected_readings"]["count"] == 3


def test_csv_upload_validates_required_header_and_accepts_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOODWATCH_LIVE_DB", str(tmp_path / "live.sqlite3"))
    assert client.post("/api/readings/upload", content="unit_id,temp_C\nR1,4").status_code == 400
    response = client.post("/api/readings/upload", content="unit_id,timestamp,temp_C\nR1,2026-10-21T12:00:00Z,4.2")
    assert response.status_code == 200
    assert response.json() == {"accepted": 1}


def test_dataset_reference_and_latest_reading_timestamps_are_explicit():
    body = client.get("/api/dashboard", params={"scenario": "stable"}).json()
    latest = body["conditions"]["temperature_summary"]["latest_timestamp_utc"]
    assert latest == body["dataset"]["reference_time_utc"]
    assert "T" in latest and latest.endswith("+00:00")
    assert body["dataset"]["freshness_reference_kind"] == "replay_reference"
    assert body["dataset"]["freshness_reference_time_utc"] == body["dataset"]["reference_time_utc"]
    live = client.get("/api/dashboard").json()
    freshness_reference = datetime.fromisoformat(live["dataset"]["freshness_reference_time_utc"])
    assert live["dataset"]["freshness_reference_kind"] == "current_time"
    assert abs((datetime.now(timezone.utc) - freshness_reference).total_seconds()) < 5
    frontend = client.get("/app.js").text
    assert "fullTimestamp(data.dataset.reference_time_utc)" in frontend


def test_dashboard_controls_have_intermediate_responsive_layout():
    css = client.get("/src/styles.css").text
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert "@media (min-width: 641px) and (max-width: 900px)" in css


def test_scenario_uses_csvs_without_live_rows_and_live_mode_still_includes_them(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOODWATCH_LIVE_DB", str(tmp_path / "live.sqlite3"))
    payload = {
        "refrigerator_id": "R1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "temperature_c": 4.6,
        "reading_valid": True,
        "source": "test-sensor",
    }
    assert client.post("/api/readings", json=payload).status_code == 201

    live = client.get("/api/dashboard", params={"refrigerator_id": "R1"}).json()
    scenario_result = client.get("/api/dashboard", params={"scenario": "stable"}).json()

    assert live["dataset"]["live_reading_count"] == 1
    assert live["conditions"]["temperature_summary"]["latest_temperature_c"] == 4.6
    assert scenario_result["dataset"]["live_reading_count"] == 0
    assert scenario_result["scenario"]["synthetic_data"] is True
    assert scenario_result["scenario"]["id"] == "stable"


def test_synthetic_warning_cycle_changes_count_and_recovers(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOODWATCH_LIVE_DB", str(tmp_path / "warning-cycle.sqlite3"))
    refrigerator_ids = ["R1", "R2", "R3"]
    expected_statuses = {
        "Normal": "within_limits",
        "Warming": "unusual_pattern",
        "Projected crossing": "approaching_limit",
        "Actual breach": "currently_out_of_range",
        "Recovery": "within_limits",
    }
    expected_counts = {
        "Normal": 0,
        "Warming": 1,
        "Projected crossing": 1,
        "Actual breach": 1,
        "Recovery": 0,
    }

    for stage, temperatures in WARNING_CYCLE:
        delete_simulated_temperature_readings(refrigerator_ids)
        now = datetime.now(timezone.utc)
        for index, refrigerator_id in enumerate(refrigerator_ids):
            values = temperatures if index == 0 else (4.0, 4.1, 3.9, 4.0)
            for offset, temperature in zip((-90, -60, -30, 0), values):
                assert record_temperature_reading(
                    refrigerator_id,
                    now + timedelta(minutes=offset),
                    temperature,
                    True,
                    "simulator-warning-cycle",
                )
        body = client.get("/api/dashboard").json()
        r1 = next(row for row in body["conditions"]["risk_forecasts"] if row["refrigerator_id"] == "R1")
        assert r1["status"] == expected_statuses[stage]
        assert body["conditions"]["temperature_warning_count"] == expected_counts[stage]
        assert body["dataset"]["synthetic_warning_cycle_active"] is True


def test_unknown_scenario_is_rejected():
    response = client.get("/api/dashboard", params={"scenario": "not-a-scenario"})
    assert response.status_code == 400
    assert "Unknown scenario" in response.json()["detail"]
