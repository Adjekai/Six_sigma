from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from bloodwatch.repository import ScenarioDataError, available_scenarios
from bloodwatch.service import build_dashboard


app = FastAPI(title="BloodWatch API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "bloodwatch-api"}


@app.get("/api/scenarios")
def scenarios() -> dict[str, list[dict]]:
    return {"scenarios": available_scenarios()}


@app.get("/api/dashboard")
def dashboard(
    scenario: str = "normal",
    site_id: str | None = None,
    refrigerator_id: str | None = None,
    temperature_window_hours: float = Query(default=24, gt=0, le=168),
    horizon_operating_days: float = Query(default=30, gt=0, le=365),
) -> dict:
    try:
        return build_dashboard(
            scenario_id=scenario,
            site_id=site_id,
            refrigerator_id=refrigerator_id,
            temperature_window_hours=temperature_window_hours,
            horizon_operating_days=horizon_operating_days,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (ScenarioDataError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


frontend = Path(__file__).resolve().parent / "frontend"
app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
