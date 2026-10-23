from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api import app


client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok", "service": "bloodwatch-api"}


def test_dashboard_frontend_is_served_without_a_build_step():
    response = client.get("/")
    assert response.status_code == 200
    assert "BloodWatch" in response.text
    assert "/app.js?v=scenario-mode-1" in response.text
    frontend = client.get("/app.js").text
    assert "loadDashboard" in frontend
    assert "Data limitations" not in frontend
    assert "Live data" in frontend
    assert "Demo · Degrading refrigerator" in frontend


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
    assert all(row["status"] in {"within_limits", "approaching_limit", "currently_out_of_range", "unknown", "insufficient_data"} for row in forecasts)


def test_scenario_endpoint_lists_the_three_dataset_demos():
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


def test_demo_scenario_uses_csvs_without_live_rows_and_live_mode_still_includes_them(tmp_path, monkeypatch):
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
    demo = client.get("/api/dashboard", params={"scenario": "stable"}).json()

    assert live["dataset"]["live_reading_count"] == 1
    assert live["conditions"]["temperature_summary"]["latest_temperature_c"] == 4.6
    assert demo["dataset"]["live_reading_count"] == 0
    assert demo["scenario"]["synthetic_demo"] is True
    assert demo["scenario"]["id"] == "stable"


def test_unknown_demo_scenario_is_rejected():
    response = client.get("/api/dashboard", params={"scenario": "not-a-scenario"})
    assert response.status_code == 400
    assert "Unknown demo scenario" in response.json()["detail"]
