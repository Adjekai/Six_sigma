from fastapi.testclient import TestClient

from api import app


client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok", "service": "bloodwatch-api"}


def test_dashboard_frontend_is_served_without_a_build_step():
    response = client.get("/")
    assert response.status_code == 200
    assert "BloodWatch" in response.text
    assert "/app.js?v=failure-callouts" in response.text
    assert "loadDashboard" in client.get("/app.js").text


def test_dashboard_uses_coherent_dataset():
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["selection"]["available_refrigerators"] == ["R1", "R2", "R3"]
    assert body["reliability"]["generators"][0]["known_demands"] == 20
    assert "scenario" not in body


def test_invalid_refrigerator_is_understandable():
    response = client.get("/api/dashboard", params={"refrigerator_id": "not-real"})
    assert response.status_code == 400
    assert "Unknown refrigerator" in response.json()["detail"]


def test_invalid_horizon_is_rejected():
    assert client.get("/api/dashboard", params={"horizon_operating_days": 0}).status_code == 422
