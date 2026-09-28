"""
GEOSHIELD — Utility Functions
Shared helpers used across multiple modules.
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

log = logging.getLogger("GeoShield.Utils")


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth (km).
    Uses the haversine formula.
    """
    R = 6371.0  # Earth radius in km
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda/2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def bbox_from_points(lats, lons, buffer_deg: float = 0.5) -> tuple:
    """
    Return (lat_min, lat_max, lon_min, lon_max) bounding box
    around a set of lat/lon points with an optional buffer.
    """
    return (
        float(np.min(lats)) - buffer_deg,
        float(np.max(lats)) + buffer_deg,
        float(np.min(lons)) - buffer_deg,
        float(np.max(lons)) + buffer_deg,
    )


def format_area(area_km2: float) -> str:
    """Human-readable area string."""
    if area_km2 >= 1_000_000:
        return f"{area_km2/1_000_000:.2f}M km²"
    if area_km2 >= 1_000:
        return f"{area_km2/1_000:.1f}K km²"
    return f"{area_km2:.1f} km²"


def safe_divide(a, b, default=0.0):
    """Division that returns `default` instead of ZeroDivisionError."""
    try:
        return a / b if b != 0 else default
    except Exception:
        return default


def df_summary(df: pd.DataFrame) -> dict:
    """Return a compact summary dict for a GEOSHIELD DataFrame."""
    return {
        "rows"          : len(df),
        "fire_count"    : int((df.get("label", pd.Series()) == 1).sum()),
        "flood_count"   : int((df.get("label", pd.Series()) == 2).sum()),
        "normal_count"  : int((df.get("label", pd.Series()) == 0).sum()),
        "high_severity" : int((df.get("severity", pd.Series()) == "High").sum()),
        "avg_frp"       : round(float(df["frp"].mean()), 2) if "frp" in df.columns else 0.0,
        "avg_confidence": round(float(df["confidence"].mean()), 2) if "confidence" in df.columns else 0.0,
        "years"         : sorted(df["year"].dropna().astype(int).unique().tolist())
                          if "year" in df.columns else [],
    }


def get_color_for_severity(severity: str) -> str:
    """Return hex color string for a severity label."""
    return {"High": "#FF2D2D", "Medium": "#FFA500", "Low": "#2ECC71"}.get(severity, "#aaaaaa")


def get_color_for_label(label: int) -> str:
    """Return hex color string for a numeric class label."""
    return {0: "#2ECC71", 1: "#FF4757", 2: "#1E90FF"}.get(label, "#aaaaaa")
