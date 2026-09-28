"""
GEOSHIELD — FastAPI REST Backend (Step 5)
Provides REST endpoints for the alert system and predictions.
"""

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config as cfg
from src.alert_system import get_all_alerts, get_alert_stats, init_db

# ── App Setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="GEOSHIELD API",
    description="AI-Powered Satellite Disaster Management REST API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure DB is initialised on startup
init_db()


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────

class PredictionRequest(BaseModel):
    brightness : float = Field(..., example=340.0, description="Channel brightness temp (K)")
    scan       : float = Field(..., example=0.75,  description="Scan pixel size (km)")
    track      : float = Field(..., example=0.75,  description="Track pixel size (km)")
    bright_t31 : float = Field(..., example=295.0, description="Band 31 brightness temp (K)")
    frp        : float = Field(..., example=50.0,  description="Fire Radiative Power (MW)")
    confidence : float = Field(75.0, example=75.0, description="Detection confidence (%)")


class PredictionResponse(BaseModel):
    label_id     : int
    label_name   : str
    confidence   : float
    probabilities: dict


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    """Health check endpoint."""
    return {
        "service"    : "GEOSHIELD API",
        "status"     : "running",
        "version"    : "1.0.0",
        "description": "AI-Powered Satellite Disaster Management System",
    }


@app.get("/api/status", tags=["Health"])
def get_status():
    """Returns system status and model availability."""
    cnn_available  = cfg.CNN_MODEL_PATH.exists()
    unet_available = cfg.UNET_MODEL_PATH.exists()
    data_available = cfg.CLEANED_DATA_PATH.exists()

    return {
        "cnn_model_ready"  : cnn_available,
        "unet_model_ready" : unet_available,
        "data_ready"       : data_available,
        "alert_db_path"    : str(cfg.ALERTS_DB_PATH),
    }


@app.post("/api/predict", response_model=PredictionResponse, tags=["Prediction"])
def predict(request: PredictionRequest):
    """
    Run AI prediction on a single VIIRS observation.
    Returns: label (Fire/Flood/Normal), confidence, probabilities.
    """
    eps  = 1e-5
    ndvi = (request.bright_t31 - request.brightness) / \
           (request.bright_t31 + request.brightness + eps)
    nbr  = (request.brightness - request.frp) / \
           (request.brightness + request.frp + eps)

    row = {
        "brightness": request.brightness,
        "scan"      : request.scan,
        "track"     : request.track,
        "bright_t31": request.bright_t31,
        "frp"       : request.frp,
        "ndvi"      : float(ndvi),
        "nbr"       : float(nbr),
    }

    try:
        from src.model_cnn import predict_single
        result = predict_single(row)
        return PredictionResponse(**result)

    except FileNotFoundError:
        # Fallback: rule-based prediction
        if request.frp > cfg.FIRE_FRP_THRESHOLD:
            label_id, label_name = 1, "Fire"
        elif request.frp < cfg.FLOOD_FRP_THRESHOLD and request.brightness < cfg.FLOOD_BRIGHT_MAX:
            label_id, label_name = 2, "Flood"
        else:
            label_id, label_name = 0, "Normal"

        return PredictionResponse(
            label_id=label_id,
            label_name=label_name,
            confidence=70.0,
            probabilities={"Normal": 10.0, "Fire": 70.0, "Flood": 20.0}
            if label_id == 1 else
            {"Normal": 15.0, "Fire": 5.0, "Flood": 80.0}
            if label_id == 2 else
            {"Normal": 80.0, "Fire": 10.0, "Flood": 10.0},
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/alerts", tags=["Alerts"])
def get_alerts(limit: int = Query(100, ge=1, le=1000)):
    """Fetch recent alerts from the database."""
    df = get_all_alerts(limit=limit)
    return JSONResponse(content=df.to_dict(orient="records"))


@app.get("/api/alerts/stats", tags=["Alerts"])
def alert_stats():
    """Return summary statistics for logged alerts."""
    return get_alert_stats()


@app.get("/api/data/summary", tags=["Data"])
def data_summary():
    """Return a summary of the loaded satellite data."""
    try:
        import pandas as pd
        if not cfg.CLEANED_DATA_PATH.exists():
            raise HTTPException(status_code=404,
                                detail="Cleaned data not found. Run the data pipeline first.")
        df = pd.read_csv(cfg.CLEANED_DATA_PATH)
        return {
            "total_rows"       : int(len(df)),
            "fire_count"       : int((df["label"] == 1).sum()),
            "flood_count"      : int((df["label"] == 2).sum()),
            "normal_count"     : int((df["label"] == 0).sum()),
            "years_covered"    : sorted(df["year"].dropna().astype(int).unique().tolist()),
            "avg_frp"          : round(float(df["frp"].mean()), 2),
            "avg_confidence"   : round(float(df["confidence"].mean()), 2),
            "total_area_km2"   : round(float((df["scan"] * df["track"]).sum()), 1),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api:app", host=cfg.API_HOST, port=cfg.API_PORT, reload=True)
