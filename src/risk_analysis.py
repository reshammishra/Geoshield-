"""
GEOSHIELD — Risk Analysis Engine (Step 3)
Classifies detections by severity (High/Medium/Low),
computes affected area, and produces year-wise trend analysis.
"""

import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")   # Non-interactive backend for server environments
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    SEVERITY_HIGH_FRP, SEVERITY_HIGH_CONF,
    SEVERITY_MED_FRP_LO, SEVERITY_MED_FRP_HI,
    SEVERITY_MED_CONF_LO, SEVERITY_MED_CONF_HI,
    SEVERITY_COLORS, REPORTS_DIR, YEARS
)

log = logging.getLogger("GeoShield.RiskAnalysis")
logging.basicConfig(level=logging.INFO,
                    format="[%(asctime)s] %(levelname)s — %(message)s",
                    datefmt="%H:%M:%S")


# ─────────────────────────────────────────────────────────────────────────────
# Severity Classification
# ─────────────────────────────────────────────────────────────────────────────

def classify_severity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'severity' column to the DataFrame.

    Rules:
      🔴 High   — FRP > 100  OR  confidence > 80
      🟡 Medium — FRP in [30,100]  OR  confidence in [60,80]
      🟢 Low    — everything else
    """
    cond_high = (df["frp"] > SEVERITY_HIGH_FRP) | (df["confidence"] > SEVERITY_HIGH_CONF)
    cond_med  = (
        (df["frp"].between(SEVERITY_MED_FRP_LO, SEVERITY_MED_FRP_HI)) |
        (df["confidence"].between(SEVERITY_MED_CONF_LO, SEVERITY_MED_CONF_HI))
    )

    severity = np.where(cond_high, "High",
               np.where(cond_med,  "Medium", "Low"))

    df["severity"] = severity

    counts = pd.Series(severity).value_counts().to_dict()
    log.info(f"Severity — High:{counts.get('High',0)}, "
             f"Medium:{counts.get('Medium',0)}, Low:{counts.get('Low',0)}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Affected Area Calculation
# ─────────────────────────────────────────────────────────────────────────────

def compute_affected_area(df: pd.DataFrame) -> pd.DataFrame:
    """
    Estimate affected area per detection.

    VIIRS pixel area ≈ scan × track km².
    We use scan and track as pixel dimensions in km.
    """
    df["area_km2"] = (df["scan"] * df["track"]).astype("float32")
    total_area = df["area_km2"].sum()
    log.info(f"Total estimated affected area: {total_area:,.1f} km²")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Year-wise Trend Analysis
# ─────────────────────────────────────────────────────────────────────────────

def compute_yearly_trends(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group by year and compute aggregate statistics.

    Returns a DataFrame with columns:
      year, total_detections, fire_count, flood_count, normal_count,
      total_area_km2, avg_frp, avg_confidence, high_severity_pct
    """
    if "label" not in df.columns:
        df["label"] = 0
    if "severity" not in df.columns:
        df = classify_severity(df)
    if "area_km2" not in df.columns:
        df = compute_affected_area(df)

    grp = df.groupby("year")

    trends = grp.agg(
        total_detections = ("frp", "count"),
        fire_count       = ("label", lambda x: (x == 1).sum()),
        flood_count      = ("label", lambda x: (x == 2).sum()),
        normal_count     = ("label", lambda x: (x == 0).sum()),
        total_area_km2   = ("area_km2", "sum"),
        avg_frp          = ("frp", "mean"),
        avg_confidence   = ("confidence", "mean"),
        high_severity_ct = ("severity", lambda x: (x == "High").sum()),
    ).reset_index()

    trends["high_severity_pct"] = (
        trends["high_severity_ct"] / trends["total_detections"] * 100
    ).round(2)

    log.info(f"Yearly trend summary:\n{trends.to_string(index=False)}")
    return trends


# ─────────────────────────────────────────────────────────────────────────────
# Report Generation (Charts)
# ─────────────────────────────────────────────────────────────────────────────

def _style_ax(ax, title, xlabel, ylabel):
    """Apply consistent dark theme styling to a matplotlib axis."""
    ax.set_facecolor("#1a1a2e")
    ax.set_title(title, color="white", fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, color="#aaaaaa", fontsize=10)
    ax.set_ylabel(ylabel, color="#aaaaaa", fontsize=10)
    ax.tick_params(colors="#aaaaaa")
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#444444")
    ax.grid(axis="y", color="#333355", alpha=0.6)


def generate_trend_charts(trends: pd.DataFrame, save: bool = True) -> list[Path]:
    """
    Generate year-wise trend visualisation charts.
    Returns list of saved PNG paths.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    years = trends["year"].astype(int).tolist()

    plt.style.use("dark_background")
    PALETTE = ["#FF4757", "#FFA502", "#2ED573"]

    # ── Chart 1: Detection counts (stacked bars) ─────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("#0f0f1a")
    width = 0.55

    fire_ct   = trends["fire_count"].tolist()
    flood_ct  = trends["flood_count"].tolist()
    normal_ct = trends["normal_count"].tolist()

    x = np.arange(len(years))
    p1 = ax.bar(x, fire_ct,   width, label="Fire",   color="#FF4757", alpha=0.9)
    p2 = ax.bar(x, flood_ct,  width, label="Flood",  color="#1E90FF", alpha=0.9,
                bottom=fire_ct)
    p3 = ax.bar(x, normal_ct, width, label="Normal", color="#2ED573", alpha=0.9,
                bottom=[f+fl for f, fl in zip(fire_ct, flood_ct)])

    ax.set_xticks(x)
    ax.set_xticklabels([str(y) for y in years], color="white")
    _style_ax(ax, "Year-wise Detection Count (2022-2024)",
              "Year", "Number of Detections")
    ax.legend(facecolor="#1a1a2e", labelcolor="white", framealpha=0.7)

    path1 = REPORTS_DIR / "trend_detections.png"
    fig.tight_layout()
    fig.savefig(path1, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    saved.append(path1)

    # ── Chart 2: Average FRP over years ──────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("#0f0f1a")

    ax.plot(years, trends["avg_frp"].tolist(), "o-",
            color="#FFA502", linewidth=2.5, markersize=8, markerfacecolor="white")
    ax.fill_between(years, trends["avg_frp"].tolist(), alpha=0.15, color="#FFA502")

    _style_ax(ax, "Average Fire Radiative Power (FRP) by Year",
              "Year", "Avg FRP (MW)")
    ax.set_xticks(years)

    path2 = REPORTS_DIR / "trend_avg_frp.png"
    fig.tight_layout()
    fig.savefig(path2, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    saved.append(path2)

    # ── Chart 3: Total affected area ─────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("#0f0f1a")

    bars = ax.bar(years, trends["total_area_km2"].tolist(),
                  color=["#FF4757", "#FFA502", "#2ED573"][:len(years)],
                  alpha=0.9, width=0.5)
    for bar, val in zip(bars, trends["total_area_km2"].tolist()):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 20,
                f"{val:,.0f}", ha="center", color="white", fontsize=9)

    _style_ax(ax, "Total Estimated Affected Area by Year",
              "Year", "Area (km²)")
    ax.set_xticks(years)

    path3 = REPORTS_DIR / "trend_area.png"
    fig.tight_layout()
    fig.savefig(path3, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    saved.append(path3)

    # ── Chart 4: High severity % ──────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("#0f0f1a")

    ax.plot(years, trends["high_severity_pct"].tolist(), "s--",
            color="#FF4757", linewidth=2, markersize=10, markerfacecolor="#ff8a8a")
    for y, v in zip(years, trends["high_severity_pct"].tolist()):
        ax.annotate(f"{v:.1f}%", (y, v), textcoords="offset points",
                    xytext=(5, 5), color="white", fontsize=9)

    _style_ax(ax, "High-Severity Event Percentage by Year",
              "Year", "High Severity (%)")
    ax.set_xticks(years)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())

    path4 = REPORTS_DIR / "trend_high_severity.png"
    fig.tight_layout()
    fig.savefig(path4, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    saved.append(path4)

    log.info(f"Saved {len(saved)} chart(s) to {REPORTS_DIR}")
    return [str(p) for p in saved]  # return plain strings for Streamlit cache compatibility


def run_risk_analysis(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    """
    Run the complete risk analysis pipeline.

    Returns
    -------
    df_risk  : DataFrame with severity + area columns
    trends   : Year-wise trend summary DataFrame
    charts   : List of saved chart paths
    """
    df_risk = classify_severity(df)
    df_risk = compute_affected_area(df_risk)
    trends  = compute_yearly_trends(df_risk)
    charts  = generate_trend_charts(trends)
    return df_risk, trends, charts


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pandas as pd
    from src.data_loader import load_all_data

    log.info("=== GEOSHIELD Risk Analysis ===")
    df = load_all_data(save=True)
    df_risk, trends, charts = run_risk_analysis(df)

    print("\n-- Yearly Trend Summary --")
    print(trends.to_string(index=False))
    print(f"\nCharts saved to: {REPORTS_DIR}")
    for c in charts:
        print(f"  -> {c}")
