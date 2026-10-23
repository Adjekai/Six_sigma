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


def test_dashboard_uses_synthetic_reference_and_full_latest_reading_timestamps():
    from datetime import datetime

    body = client.get("/api/dashboard", params={"scenario": "stable"}).json()
    reference = datetime.fromisoformat(body["dataset"]["reference_time_utc"])
    latest = datetime.fromisoformat(body["conditions"]["temperature_summary"]["latest_timestamp_utc"])
    assert reference.tzinfo is not None
    assert latest.tzinfo is not None
    assert latest <= reference

    script = client.get("/app.js").text
    assert "Synthetic dataset reference time:" in script
    assert "Latest temperature reading" in script
    assert "const fullTimestamp = time => new Intl.DateTimeFormat" in script
    assert "timeZone:'UTC'" in script
    assert "timeZoneName:'short'" in script
    assert "Current time:" not in script
    assert script.count("fridge.failure_probability") == 1
    assert script.count("generator.failed_start_probability") == 1
    assert '<details class="methods-details"><summary>Methods and details</summary>' in script


def test_scenario_controls_are_above_inventory_and_wrap_at_medium_widths():
    script = client.get("/app.js").text
    render = script.split("function render() {", 1)[1].split("async function loadDashboard()", 1)[0]
    assert render.index('<section class="controls"') < render.index("scenarioPanel(data.scenario)")
    assert render.index("scenarioPanel(data.scenario)") < render.index("content?.overviewPanel")

    styles = client.get("/src/styles.css").text
    assert ".controls { display: flex; flex-wrap: wrap;" in styles
    assert "@media (min-width: 641px) and (max-width: 900px) { .controls { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); } }" in styles
