from fastapi.testclient import TestClient

from api import app


client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok", "service": "bloodwatch-api"}


def test_dashboard_frontend_is_served_without_a_build_step():
    response = client.get("/")
    assert response.status_code == 200
    assert "BloodWatch" in response.text
    assert "/app.js" in response.text

    javascript = client.get("/app.js")
    assert javascript.status_code == 200
    assert "loadDashboard" in javascript.text


def test_scenarios():
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    assert len(response.json()["scenarios"]) == 3


def test_dashboard():
    response = client.get("/api/dashboard", params={"scenario": "blackout_failed_backup"})
    assert response.status_code == 200
    assert response.json()["reliability"]["generators"][0]["known_demands"] == 20


def test_invalid_scenario_is_understandable():
    response = client.get("/api/dashboard", params={"scenario": "not_real"})
    assert response.status_code == 404
    assert "Unknown scenario" in response.json()["detail"]


def test_invalid_horizon_is_rejected():
    response = client.get("/api/dashboard", params={"horizon_operating_days": 0})
    assert response.status_code == 422
