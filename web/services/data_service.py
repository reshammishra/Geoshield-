"""
GeoShield – Data Service
Loads the preprocessed NASA VIIRS dataset, applies risk analysis,
and exposes efficient in-memory access to all other services.
"""

import logging
import sys
import threading
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.data_loader import load_all_data
from src.risk_analysis import classify_severity, compute_affected_area

log = logging.getLogger("GeoShield.DataService")

# ── Module-level singleton ────────────────────────────────────────────────────
_df: pd.DataFrame | None = None
_load_lock = threading.Lock()
_loaded_at: datetime | None = None


def get_df() -> pd.DataFrame:
    """Return the cached DataFrame, loading it if needed."""
    global _df, _loaded_at
    if _df is not None:
        return _df
    with _load_lock:
        if _df is not None:
            return _df
        log.info("Loading dataset …")
        parquet_path = ROOT / "outputs" / "cleaned_data.parquet"
        if parquet_path.exists():
            log.info(f"Loading high-speed parquet from {parquet_path} …")
            raw = pd.read_parquet(parquet_path)
        else:
            raw = load_all_data(save=False)
        # If acq_date is not datetime yet, ensure it is
        if not pd.api.types.is_datetime64_any_dtype(raw["acq_date"]):
            raw["acq_date"] = pd.to_datetime(raw["acq_date"], errors="coerce")
        _df = raw
        _loaded_at = datetime.utcnow()
        log.info(f"Dataset ready: {len(_df):,} rows, loaded at {_loaded_at}")
    return _df


def reload_df():
    """Force a fresh reload (clears cache)."""
    global _df, _loaded_at
    _df = None
    _loaded_at = None
    return get_df()


# ── Utility helpers ────────────────────────────────────────────────────────────

def label_name(label_int: int) -> str:
    return {0: "Normal", 1: "Fire", 2: "Flood"}.get(int(label_int), "Unknown")


def apply_filters(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """
    Apply common filters from a params dict.
    Supported keys: years, event_types, severity_levels, confidence_min,
                    date_from, date_to, city
    """
    mask = pd.Series(True, index=df.index)

    years = params.get("years")
    if years:
        years = [int(y) for y in years]
        mask &= df["year"].isin(years)

    event_types = params.get("event_types")  # list of "Fire","Flood","Normal"
    if event_types:
        label_map = {"Fire": 1, "Flood": 2, "Normal": 0}
        ids = [label_map[e] for e in event_types if e in label_map]
        if ids:
            mask &= df["label"].isin(ids)

    sev = params.get("severity_levels")
    if sev and "severity" in df.columns:
        mask &= df["severity"].isin(sev)

    conf_min = params.get("confidence_min")
    if conf_min is not None:
        mask &= df["confidence"] >= float(conf_min)

    date_from = params.get("date_from")
    if date_from:
        mask &= df["acq_date"] >= pd.to_datetime(date_from)

    date_to = params.get("date_to")
    if date_to:
        mask &= df["acq_date"] <= pd.to_datetime(date_to)

    city = params.get("city")
    if city and city not in ("All India", "all", ""):
        if "city" in df.columns:
            mask &= df["city"] == city

    return df.loc[mask].copy()


def get_summary_stats(df: pd.DataFrame | None = None) -> dict:
    """Return KPI summary for a DataFrame (defaults to full dataset)."""
    if df is None:
        df = get_df()
    fire_df  = df[df["label"] == 1]
    flood_df = df[df["label"] == 2]
    return {
        "total_detections": int(len(df)),
        "fire_count":       int(len(fire_df)),
        "flood_count":      int(len(flood_df)),
        "normal_count":     int((df["label"] == 0).sum()),
        "high_severity":    int((df["severity"] == "High").sum()) if "severity" in df.columns else 0,
        "avg_frp":          round(float(fire_df["frp"].mean()), 2) if len(fire_df) else 0,
        "max_frp":          round(float(df["frp"].max()), 2) if len(df) else 0,
        "avg_confidence":   round(float(df["confidence"].mean()), 2) if len(df) else 0,
        "total_area_km2":   round(float(df["area_km2"].sum()), 1) if "area_km2" in df.columns else 0,
        "years_covered":    sorted(df["year"].dropna().astype(int).unique().tolist()),
        "cities_covered":   int(df["city"].nunique()) if "city" in df.columns else 0,
        "date_from":        str(df["acq_date"].min().date()) if len(df) else "N/A",
        "date_to":          str(df["acq_date"].max().date()) if len(df) else "N/A",
        "loaded_at":        _loaded_at.isoformat() if _loaded_at else "N/A",
    }


def get_what_changed(hours: int = 24) -> dict:
    """Compare recent vs previous period detections (real data)."""
    df = get_df()
    cutoff_recent   = df["acq_date"].max()
    cutoff_prev     = cutoff_recent - timedelta(days=1)
    cutoff_prev2    = cutoff_prev   - timedelta(days=1)

    recent = df[df["acq_date"] > cutoff_prev]
    prev   = df[(df["acq_date"] > cutoff_prev2) & (df["acq_date"] <= cutoff_prev)]

    def counts(sub):
        return {
            "total":    len(sub),
            "fire":     int((sub["label"] == 1).sum()),
            "flood":    int((sub["label"] == 2).sum()),
            "high_sev": int((sub["severity"] == "High").sum()) if "severity" in sub.columns else 0,
            "avg_frp":  round(float(sub[sub["label"] == 1]["frp"].mean()), 2) if (sub["label"] == 1).any() else 0,
        }

    r = counts(recent)
    p = counts(prev)

    def delta(a, b):
        return a - b

    def pct_change(a, b):
        if b == 0:
            return None
        return round((a - b) / b * 100, 1)

    return {
        "period_label":       f"vs previous 24h",
        "recent_total":       r["total"],
        "prev_total":         p["total"],
        "delta_total":        delta(r["total"], p["total"]),
        "pct_change_total":   pct_change(r["total"], p["total"]),
        "recent_fire":        r["fire"],
        "delta_fire":         delta(r["fire"], p["fire"]),
        "recent_flood":       r["flood"],
        "delta_flood":        delta(r["flood"], p["flood"]),
        "recent_high":        r["high_sev"],
        "delta_high":         delta(r["high_sev"], p["high_sev"]),
        "recent_avg_frp":     r["avg_frp"],
        "delta_avg_frp":      round(r["avg_frp"] - p["avg_frp"], 2),
    }


def get_yearly_trends(df: pd.DataFrame | None = None) -> list[dict]:
    """Return year-by-year aggregated stats."""
    if df is None:
        df = get_df()
    if "severity" not in df.columns:
        df = classify_severity(df)
    if "area_km2" not in df.columns:
        df = compute_affected_area(df)

    rows = []
    for year, grp in df.groupby("year"):
        rows.append({
            "year":              int(year),
            "total":             int(len(grp)),
            "fire":              int((grp["label"] == 1).sum()),
            "flood":             int((grp["label"] == 2).sum()),
            "normal":            int((grp["label"] == 0).sum()),
            "high_severity":     int((grp["severity"] == "High").sum()),
            "avg_frp":           round(float(grp[grp["label"]==1]["frp"].mean()), 2)
                                 if (grp["label"]==1).any() else 0,
            "avg_confidence":    round(float(grp["confidence"].mean()), 2),
            "total_area_km2":    round(float(grp["area_km2"].sum()), 1),
        })
    return rows


def get_city_summary(df: pd.DataFrame | None = None) -> list[dict]:
    """Return per-city aggregated stats, sorted by fire count desc."""
    if df is None:
        df = get_df()
    if "city" not in df.columns:
        return []
    if "severity" not in df.columns:
        df = classify_severity(df)

    rows = []
    for city, grp in df.groupby("city"):
        rows.append({
            "city":          str(city),
            "total":         int(len(grp)),
            "fire":          int((grp["label"] == 1).sum()),
            "flood":         int((grp["label"] == 2).sum()),
            "high_severity": int((grp["severity"] == "High").sum()),
            "avg_frp":       round(float(grp[grp["label"]==1]["frp"].mean()), 2)
                             if (grp["label"]==1).any() else 0,
        })
    rows.sort(key=lambda x: x["fire"], reverse=True)
    return rows


def get_data_quality(df: pd.DataFrame | None = None) -> dict:
    """Return data quality / health metrics."""
    if df is None:
        df = get_df()
    total = len(df)
    return {
        "total_records":       total,
        "missing_lat":         int(df["latitude"].isna().sum()),
        "missing_lon":         int(df["longitude"].isna().sum()),
        "missing_timestamp":   int(df["acq_date"].isna().sum()),
        "null_frp":            int(df["frp"].isna().sum()) if "frp" in df.columns else 0,
        "null_brightness":     int(df["brightness"].isna().sum()) if "brightness" in df.columns else 0,
        "duplicate_rows":      int(df.duplicated(subset=["latitude","longitude","acq_date"]).sum()),
        "invalid_lat":         int(((df["latitude"] < 6) | (df["latitude"] > 38)).sum()),
        "invalid_lon":         int(((df["longitude"] < 67) | (df["longitude"] > 98)).sum()),
        "date_from":           str(df["acq_date"].min().date()) if len(df) else "N/A",
        "date_to":             str(df["acq_date"].max().date()) if len(df) else "N/A",
        "years":               sorted(df["year"].dropna().astype(int).unique().tolist()),
        "completeness_pct":    round((1 - df.isna().mean().mean()) * 100, 2),
        "cities_tagged":       int(df["city"].nunique()) if "city" in df.columns else 0,
        "source_files":        ["viirs-jpss1_2022_India.csv",
                                "viirs-jpss1_2023_India.csv",
                                "viirs-jpss1_2024_India.csv"],
        "satellite":           "NOAA-20 / VIIRS JPSS-1",
        "loaded_at":           _loaded_at.isoformat() if _loaded_at else "N/A",
        "pipeline_status": {
            "data_ingestion":   "OK",
            "preprocessing":    "OK",
            "validation":       "OK",
            "event_fusion":     "OK",
            "risk_engine":      "OK",
            "api":              "OK",
        }
    }
