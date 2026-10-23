from __future__ import annotations

import math
import csv
import io
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, model_validator
from fastapi.staticfiles import StaticFiles

from bloodwatch.live_data import record_temperature_reading, record_rejected_reading
from bloodwatch.repository import DatasetError, known_refrigerator_ids
from bloodwatch.scenarios import scenario_options
from bloodwatch.service import build_dashboard


app = FastAPI(title="BloodWatch API", version="0.1.0")
LIVE_MIN_C = -50.0
LIVE_MAX_C = 50.0
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def track_invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
    if request.url.path.startswith("/api/readings"):
        messages = "; ".join(item["msg"] for item in error.errors())
        record_rejected_reading(messages or "Invalid reading payload")
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": error.errors()}))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "bloodwatch-api"}


@app.get("/api/dashboard")
def dashboard(
    refrigerator_id: str | None = None,
    temperature_window_hours: float = Query(default=24, gt=0, le=168),
    horizon_operating_days: float = Query(default=30, gt=0, le=365),
    scenario: str | None = None,
    lower_limit_c: float = Query(default=1, ge=-50, le=50),
    upper_limit_c: float = Query(default=6, ge=-50, le=50),
) -> dict:
    try:
        return build_dashboard(
            refrigerator_id=refrigerator_id,
            temperature_window_hours=temperature_window_hours,
            horizon_operating_days=horizon_operating_days,
            scenario=scenario,
            lower_limit_c=lower_limit_c,
            upper_limit_c=upper_limit_c,
        )
    except (DatasetError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/scenarios")
def scenarios() -> list[dict[str, str]]:
    return scenario_options()


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
        if self.temperature_c is None:
            raise ValueError("temperature_c is required for every incoming reading")
        if not self.reading_valid:
            raise ValueError("Incoming readings must be valid; correct invalid data before submission")
        if self.temperature_c is not None and not math.isfinite(self.temperature_c):
            raise ValueError("temperature_c must be finite")
        if self.temperature_c is not None and not LIVE_MIN_C <= self.temperature_c <= LIVE_MAX_C:
            raise ValueError(f"temperature_c must be between {LIVE_MIN_C:g} and {LIVE_MAX_C:g} °C")
        if not self.refrigerator_id.strip() or not self.source.strip():
            raise ValueError("refrigerator_id and source must not be blank")
        return self


@app.post("/api/readings", status_code=status.HTTP_201_CREATED)
def ingest_reading(reading: TemperatureReading) -> dict[str, str]:
    try:
        if reading.timestamp_utc.astimezone(timezone.utc) > datetime.now(timezone.utc):
            record_rejected_reading("Timestamp is in the future")
            raise HTTPException(status_code=400, detail="Timestamp must not be in the future")
        if reading.refrigerator_id not in known_refrigerator_ids():
            record_rejected_reading("Unknown unit_id")
            raise HTTPException(status_code=400, detail=f"Unknown refrigerator: {reading.refrigerator_id}")
        inserted = record_temperature_reading(
            refrigerator_id=reading.refrigerator_id,
            timestamp=reading.timestamp_utc.astimezone(timezone.utc),
            temperature_c=reading.temperature_c,
            reading_valid=reading.reading_valid,
            source=reading.source,
        )
        if not inserted:
            record_rejected_reading("Duplicate unit and timestamp")
            raise HTTPException(status_code=409, detail="Duplicate reading for this unit and timestamp")
        return {"status": "accepted", "refrigerator_id": reading.refrigerator_id}
    except (DatasetError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/readings/upload")
async def upload_readings(request: Request) -> dict[str, int]:
    text = (await request.body()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    required = {"unit_id", "timestamp", "temp_C"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise HTTPException(status_code=400, detail="CSV requires columns: unit_id, timestamp, temp_C")
    accepted = 0
    for line, row in enumerate(reader, start=2):
        try:
            item = TemperatureReading(
                refrigerator_id=row["unit_id"],
                timestamp_utc=datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                temperature_c=float(row["temp_C"]),
                source="csv-upload",
            )
            ingest_reading(item)
            accepted += 1
        except Exception as error:
            detail = error.detail if isinstance(error, HTTPException) else str(error)
            raise HTTPException(status_code=400, detail=f"CSV row {line}: {detail}") from error
    return {"accepted": accepted}


frontend = Path(__file__).resolve().parent / "frontend"
app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
