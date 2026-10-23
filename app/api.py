from __future__ import annotations

import math
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, model_validator
from fastapi.staticfiles import StaticFiles

from bloodwatch.live_data import record_temperature_reading
from bloodwatch.repository import DatasetError, known_refrigerator_ids
from bloodwatch.service import build_dashboard


app = FastAPI(title="BloodWatch API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "bloodwatch-api"}


@app.get("/api/dashboard")
def dashboard(
    refrigerator_id: str | None = None,
    temperature_window_hours: float = Query(default=24, gt=0, le=168),
    horizon_operating_days: float = Query(default=30, gt=0, le=365),
) -> dict:
    try:
        return build_dashboard(
            refrigerator_id=refrigerator_id,
            temperature_window_hours=temperature_window_hours,
            horizon_operating_days=horizon_operating_days,
        )
    except (DatasetError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


class TemperatureReading(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refrigerator_id: str
    timestamp_utc: datetime
    temperature_c: float | None
    reading_valid: bool = True
    source: str = "sensor"

    @model_validator(mode="after")
    def validate_reading(self) -> TemperatureReading:
        if self.timestamp_utc.tzinfo is None:
            raise ValueError("timestamp_utc must include a timezone")
        if self.reading_valid != (self.temperature_c is not None):
            raise ValueError("Valid readings require a temperature; invalid readings must use null")
        if self.temperature_c is not None and not math.isfinite(self.temperature_c):
            raise ValueError("temperature_c must be finite")
        if not self.refrigerator_id.strip() or not self.source.strip():
            raise ValueError("refrigerator_id and source must not be blank")
        return self


@app.post("/api/readings", status_code=status.HTTP_201_CREATED)
def ingest_reading(reading: TemperatureReading) -> dict[str, str]:
    try:
        if reading.refrigerator_id not in known_refrigerator_ids():
            raise HTTPException(status_code=400, detail=f"Unknown refrigerator: {reading.refrigerator_id}")
        record_temperature_reading(
            refrigerator_id=reading.refrigerator_id,
            timestamp=reading.timestamp_utc.astimezone(timezone.utc),
            temperature_c=reading.temperature_c,
            reading_valid=reading.reading_valid,
            source=reading.source,
        )
        return {"status": "accepted", "refrigerator_id": reading.refrigerator_id}
    except (DatasetError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


frontend = Path(__file__).resolve().parent / "frontend"
app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
