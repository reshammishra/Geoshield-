"""
GEOSHIELD — Streamlit Dashboard (Step 4)
Main interactive web application for the disaster management system.
Real NASA VIIRS JPSS-1 India data integration with city search.
"""

import io
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import folium
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as st_components

warnings.filterwarnings("ignore")

# ── Project root ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import config as cfg
from src.data_loader   import load_all_data
from src.risk_analysis import run_risk_analysis, classify_severity, compute_affected_area
from src.map_builder   import build_map
from src.alert_system  import (get_all_alerts, get_alert_stats,
                                init_db, log_alert)

# ─────────────────────────────────────────────────────────────────────────────
# Page Configuration
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="GEOSHIELD — AI Disaster Management",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "GEOSHIELD v1.0 | AI-Powered Satellite Disaster Management"},
)

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
  /* ── GEOSHIELD Professional Theme (Navy + White) ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  .stApp {
    background: #f0f4f8;
    color: #0f172a;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  }

  /* Hide default header */
  header[data-testid="stHeader"] { background: transparent !important; }
  .stAppHeader { display: none !important; }

  /* ── Top Header Bar ── */
  .geo-topbar {
    background: linear-gradient(90deg, #0e2a3d 0%, #1a4b8c 60%, #0e2a3d 100%);
    padding: 0 2rem;
    height: 52px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 3px solid #f59e0b;
    margin-bottom: 0;
  }
  .geo-topbar-brand {
    display: flex; align-items: center; gap: 10px;
    color: #ffffff; font-weight: 800; font-size: 18px; letter-spacing: -0.02em;
  }
  .geo-topbar-right {
    display: flex; align-items: center; gap: 1rem;
    font-size: 12px; color: #94a3b8;
  }
  .geo-badge-live {
    background: rgba(16,185,129,0.2); color: #34d399;
    border: 1px solid #34d399; border-radius: 20px;
    padding: 2px 10px; font-size: 11px; font-weight: 700; letter-spacing: 0.05em;
  }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #dbe4f0 !important;
  }
  [data-testid="stSidebar"] .stMarkdown p { color: #475569 !important; }
  [data-testid="stSidebar"] label { color: #0f172a !important; font-weight: 600 !important; }
  [data-testid="stSidebar"] .stSelectbox label,
  [data-testid="stSidebar"] .stMultiSelect label,
  [data-testid="stSidebar"] .stSlider label { color: #334155 !important; font-size: 13px !important; }

  /* ── Metric Cards ── */
  [data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #dbe4f0;
    border-radius: 10px;
    padding: 16px;
    box-shadow: 0 1px 4px rgba(14,42,61,0.08);
    border-left: 4px solid #1a4b8c;
  }
  [data-testid="stMetric"] label {
    color: #64748b !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  [data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #0e2a3d !important;
    font-size: 26px !important;
    font-weight: 800 !important;
  }

  /* ── Tabs ── */
  .stTabs [data-baseweb="tab-list"] {
    background: #ffffff;
    border-radius: 10px;
    padding: 6px;
    gap: 4px;
    border: 1px solid #dbe4f0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }
  .stTabs [data-baseweb="tab"] {
    border-radius: 7px;
    color: #475569;
    font-weight: 600;
    font-size: 13px;
    padding: 8px 18px;
    border: none;
  }
  .stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #0e2a3d, #1a4b8c) !important;
    color: white !important;
    box-shadow: 0 2px 8px rgba(14,42,61,0.3);
  }

  /* ── Buttons ── */
  .stButton > button {
    background: linear-gradient(135deg, #0e2a3d, #1a4b8c);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 700;
    font-size: 14px;
    padding: 10px 24px;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(14,42,61,0.3);
  }
  .stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(14,42,61,0.4);
    background: linear-gradient(135deg, #1a4b8c, #0e2a3d);
  }

  /* ── Section Headers ── */
  .section-header {
    background: #ffffff;
    border-left: 4px solid #1a4b8c;
    border-radius: 0 8px 8px 0;
    padding: 10px 18px;
    margin: 16px 0 12px 0;
    color: #0e2a3d;
    font-weight: 700;
    font-size: 16px;
    border: 1px solid #dbe4f0;
    border-left: 4px solid #1a4b8c;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
  }

  /* ── Hero Banner ── */
  .hero-banner {
    background: linear-gradient(135deg, #0e2a3d 0%, #1a4b8c 60%, #0e2a3d 100%);
    padding: 36px 48px;
    border-radius: 16px;
    margin-bottom: 24px;
    text-align: center;
    box-shadow: 0 8px 32px rgba(14,42,61,0.25);
    position: relative;
    overflow: hidden;
    border-bottom: 3px solid #f59e0b;
  }
  .hero-banner::before {
    content: '';
    position: absolute;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(ellipse at center, rgba(245,158,11,0.08) 0%, transparent 70%);
    pointer-events: none;
  }

  /* ── Cards ── */
  .geo-card {
    background: #ffffff;
    border: 1px solid #dbe4f0;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 12px;
    box-shadow: 0 1px 4px rgba(14,42,61,0.07);
  }
  .geo-card-fire   { border-left: 4px solid #dc2626; }
  .geo-card-flood  { border-left: 4px solid #1d4ed8; }
  .geo-card-normal { border-left: 4px solid #16a34a; }
  .geo-card-high   { border-left: 4px solid #dc2626; background: #fff5f5; }

  /* ── Badges ── */
  .badge { display:inline-block; border-radius:20px; padding:2px 10px;
           font-size:11px; font-weight:700; letter-spacing:0.04em; }
  .badge-fire   { background:#fee2e2; color:#dc2626; border:1px solid #fca5a5; }
  .badge-flood  { background:#dbeafe; color:#1d4ed8; border:1px solid #93c5fd; }
  .badge-normal { background:#dcfce7; color:#16a34a; border:1px solid #86efac; }
  .badge-high   { background:#fee2e2; color:#dc2626; }
  .badge-medium { background:#fef3c7; color:#d97706; }
  .badge-low    { background:#dcfce7; color:#16a34a; }
  .badge-navy   { background:#dbeafe; color:#1e3a8a; }
  .badge-amber  { background:#fef3c7; color:#92400e; border:1px solid #f59e0b; }

  /* ── Alert Cards ── */
  .alert-high   { background: #fff5f5; border:1px solid #fca5a5; border-left:4px solid #dc2626; }
  .alert-medium { background: #fffbeb; border:1px solid #fcd34d; border-left:4px solid #f59e0b; }
  .alert-low    { background: #f0fdf4; border:1px solid #86efac; border-left:4px solid #16a34a; }
  .alert-card {
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
    font-size: 13px;
    color: #1e293b;
  }

  /* ── Ticker ── */
  .ticker-item {
    background: #fff5f5;
    border-left: 3px solid #dc2626;
    border-radius: 0 8px 8px 0;
    padding: 8px 12px;
    margin-bottom: 6px;
    font-size: 12px;
    color: #1e293b;
  }

  /* ── Season banners ── */
  .season-fire {
    background: #fff7ed;
    border: 1px solid #fb923c;
    border-left: 4px solid #ea580c;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 8px 0;
    font-size: 12px;
    color: #7c2d12;
  }
  .season-monsoon {
    background: #eff6ff;
    border: 1px solid #60a5fa;
    border-left: 4px solid #2563eb;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 8px 0;
    font-size: 12px;
    color: #1e3a8a;
  }
  .season-winter {
    background: #f5f3ff;
    border: 1px solid #a78bfa;
    border-left: 4px solid #7c3aed;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 8px 0;
    font-size: 12px;
    color: #4c1d95;
  }

  /* ── City card ── */
  .city-card {
    background: #ffffff;
    border: 1px solid #dbe4f0;
    border-radius: 10px;
    padding: 16px 20px;
    margin: 8px 0;
    border-left: 4px solid #1a4b8c;
  }

  /* ── Tables ── */
  .stDataFrame { border-radius: 10px; overflow: hidden; border: 1px solid #dbe4f0; }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: #f1f5f9; }
  ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

  /* ── Progress bar ── */
  .stProgress > div > div { background: linear-gradient(90deg, #1a4b8c, #3b82f6); }

  /* ── Info/warning/error boxes ── */
  .stAlert { border-radius: 8px; }
  [data-testid="stNotification"] { border-radius: 8px; }

  /* ── Inputs ── */
  .stTextInput input, .stSelectbox select {
    border: 1px solid #dbe4f0 !important;
    border-radius: 7px !important;
    background: #ffffff !important;
    color: #0f172a !important;
  }
  .stTextInput input:focus { border-color: #1a4b8c !important; box-shadow: 0 0 0 2px rgba(26,75,140,0.15) !important; }

  /* ── Plotly chart containers ── */
  .js-plotly-plot { border-radius: 10px; }

  /* ── Dividers ── */
  hr { border-color: #e2e8f0 !important; }

  /* ── Download buttons ── */
  .stDownloadButton > button {
    background: #ffffff;
    color: #1a4b8c;
    border: 1px solid #1a4b8c;
    border-radius: 8px;
    font-weight: 600;
  }
  .stDownloadButton > button:hover { background: #eff6ff; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Cached Data Loading
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=3600)
def get_data():
    """Load and process all data (cached for 1 hour)."""
    df = load_all_data(save=True)
    df_risk, trends, charts = run_risk_analysis(df)
    return df_risk, trends, charts


@st.cache_data(show_spinner=False)
def get_cnn_model():
    """Load CNN model if available."""
    try:
        from src.model_cnn import load_cnn_model
        model, scaler = load_cnn_model()
        return model, scaler
    except FileNotFoundError:
        return None, None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_season_info() -> dict:
    """Return current fire season classification for India."""
    month = datetime.now().month
    if month in [3, 4, 5, 6]:
        return {
            "season": "🔥 Peak Fire Season",
            "desc": "March–June: Dry conditions, high fire risk across central & north India.",
            "class": "season-fire",
            "risk": "HIGH",
            "color": "#FF4757",
        }
    elif month in [7, 8, 9]:
        return {
            "season": "🌧️ Monsoon Season",
            "desc": "July–September: Rainfall reduces fire activity. Flood risk elevated.",
            "class": "season-monsoon",
            "risk": "LOW FIRE / HIGH FLOOD",
            "color": "#1E90FF",
        }
    elif month in [10, 11]:
        return {
            "season": "🌾 Post-Monsoon / Stubble Burning",
            "desc": "Oct–Nov: Crop residue burning peaks in Punjab, Haryana, UP.",
            "class": "season-fire",
            "risk": "MEDIUM-HIGH",
            "color": "#FFA502",
        }
    else:
        return {
            "season": "❄️ Winter Season",
            "desc": "December–February: Lower fire activity, but industrial hotspots persist.",
            "class": "season-winter",
            "risk": "LOW",
            "color": "#9370DB",
        }


def _filter_city(df: pd.DataFrame, city_name: str, radius_km: float = None) -> pd.DataFrame:
    """Filter DataFrame to a specific Indian city using lat/lon bounding box."""
    if city_name == "All India" or city_name not in cfg.INDIA_CITIES:
        return df
    city_info = cfg.INDIA_CITIES[city_name]
    if city_info is None:
        return df
    clat, clon, default_rad = city_info
    rad = (radius_km / 111.0) if radius_km else default_rad
    return df[
        df["latitude"].between(clat - rad, clat + rad) &
        df["longitude"].between(clon - rad, clon + rad)
    ].copy()


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar(df_full: pd.DataFrame):
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding:16px 0 8px 0;">
          <div style="font-size:48px;">🛡️</div>
          <h1 style="color:#00d2ff; margin:0; font-size:22px; font-weight:800;">GEOSHIELD</h1>
          <p style="color:#7fa8c8; font-size:12px; margin:4px 0;">
            AI Satellite Disaster Management
          </p>
          <p style="color:#4a7a9b; font-size:10px; margin:2px 0;">
            🇮🇳 India · NASA VIIRS JPSS-1
          </p>
        </div>
        <hr style="border-color:#1e3a5f; margin:12px 0;">
        """, unsafe_allow_html=True)

        # ── Season Alert ─────────────────────────────────────────────────────
        season_info = _get_season_info()
        st.markdown(f"""
        <div class="{season_info['class']}">
          <b style="color:{season_info['color']};">{season_info['season']}</b><br>
          <span style="font-size:11px; color:#ccc;">{season_info['desc']}</span><br>
          <span style="font-size:11px;">Risk Level: <b style="color:{season_info['color']};">{season_info['risk']}</b></span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("**📅 Data Filters**")
        selected_years = st.multiselect(
            "Select Years",
            options=[2022, 2023, 2024],
            default=[2022, 2023, 2024],
        )

        selected_labels = st.multiselect(
            "Event Types",
            options=["Fire", "Flood", "Normal"],
            default=["Fire", "Flood"],
        )

        selected_severity = st.multiselect(
            "Severity Levels",
            options=["High", "Medium", "Low"],
            default=["High", "Medium", "Low"],
        )

        conf_min = st.slider("Min Confidence (%)", 50, 100, 50, step=5)

        st.markdown("---")
        st.markdown("**🗺️ Map Options**")
        max_markers = st.slider("Max Map Markers", 200, 2000, 500, step=100)

        st.markdown("---")
        st.markdown("**🏙️ City Explorer**")
        city_options = list(cfg.INDIA_CITIES.keys())
        selected_city = st.selectbox(
            "Jump to City",
            options=city_options,
            index=0,
            help="Select an Indian city to view its fire records",
        )

        # ── Live fire ticker ──────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**🔴 Latest Fire Detections**")
        try:
            _ticker_cols = ["acq_date", "latitude", "longitude", "frp", "severity"]
            if "city" in df_full.columns:
                _ticker_cols.append("city")
            recent = (
                df_full[df_full["label"] == 1]
                .sort_values("acq_date", ascending=False)
                .head(5)
                [_ticker_cols]
            )
            if not recent.empty:
                for _, row in recent.iterrows():
                    city_str = str(row["city"]) if "city" in row.index else ""
                    city_tag = f" [{city_str}]" if city_str and city_str != "Other" else ""
                    st.markdown(f"""
                    <div class="ticker-item">
                      🔥 {str(row['acq_date'])[:10]}{city_tag}<br>
                      <span style="color:#aaa; font-size:11px;">
                        Lat {row['latitude']:.2f}, Lon {row['longitude']:.2f} |
                        FRP: <b>{row['frp']:.0f} MW</b> | {row['severity']}
                      </span>
                    </div>
                    """, unsafe_allow_html=True)
        except Exception:
            st.caption("No recent fire data.")

        st.markdown("---")
        st.markdown("""
        <div style="font-size:11px; color:#555; text-align:center; padding-top:8px;">
          GEOSHIELD v1.0 | NASA VIIRS JPSS-1<br>
          🇮🇳 India Data: 2022 · 2023 · 2024
        </div>
        """, unsafe_allow_html=True)

    return selected_years, selected_labels, selected_severity, conf_min, max_markers, selected_city


# ─────────────────────────────────────────────────────────────────────────────
# Tab 1 — Overview / KPI
# ─────────────────────────────────────────────────────────────────────────────

def render_overview(df: pd.DataFrame, trends: pd.DataFrame):
    # Hero banner
    st.markdown("""
    <div class="hero-banner">
      <h1 style="color:white; font-size:32px; margin:0; font-weight:900;
                 text-shadow:0 0 30px rgba(0,210,255,0.5);">
        🛡️ GEOSHIELD
      </h1>
      <p style="color:rgba(255,255,255,0.8); font-size:16px; margin:8px 0 0 0;">
        AI-Powered Satellite Disaster Management System
      </p>
      <p style="color:rgba(0,210,255,0.7); font-size:13px; margin:4px 0 0 0;">
        Real-time Wildfire Detection · NASA VIIRS JPSS-1 · India 2022–2024
      </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Real-time Fire Intensity Gauge ──────────────────────────────────────
    max_frp = float(df[df["label"] == 1]["frp"].max()) if (df["label"] == 1).any() else 0
    avg_frp = float(df[df["label"] == 1]["frp"].mean()) if (df["label"] == 1).any() else 0

    gauge_fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=avg_frp,
        delta={"reference": 10, "valueformat": ".1f"},
        title={"text": "Avg Fire Intensity (FRP MW)", "font": {"color": "white", "size": 14}},
        number={"suffix": " MW", "font": {"color": "#FFA502", "size": 28}},
        gauge={
            "axis": {"range": [0, max(max_frp, 100)], "tickcolor": "#aaa", "tickfont": {"color": "#aaa"}},
            "bar": {"color": "#FFA502"},
            "bgcolor": "#0f0f1a",
            "borderwidth": 1,
            "bordercolor": "#1e3a5f",
            "steps": [
                {"range": [0, 50],  "color": "rgba(46,204,113,0.3)"},
                {"range": [50, 150], "color": "rgba(255,165,0,0.3)"},
                {"range": [150, max(max_frp, 151)], "color": "rgba(255,45,45,0.3)"},
            ],
            "threshold": {"line": {"color": "#FF4757", "width": 4}, "value": max(max_frp * 0.8, 1)},
        }
    ))
    gauge_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        height=220,
        margin=dict(t=30, b=10, l=20, r=20),
    )

    # ── KPI Metrics ────────────────────────────────────────────────────────
    fire_ct   = int((df["label"] == 1).sum())
    flood_ct  = int((df["label"] == 2).sum())
    high_ct   = int((df["severity"] == "High").sum())
    total_km2 = float(df["area_km2"].sum()) if "area_km2" in df.columns else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📊 Total Detections", f"{len(df):,}")
    c2.metric("🔥 Fire Events",      f"{fire_ct:,}")
    c3.metric("🌊 Flood Events",     f"{flood_ct:,}")
    c4.metric("🔴 High Severity",    f"{high_ct:,}")
    c5.metric("📐 Area Affected",    f"{total_km2:,.0f} km²")

    st.markdown("<br>", unsafe_allow_html=True)

    col_gauge, col_right = st.columns([1, 2])
    with col_gauge:
        st.markdown('<div class="section-header">⚡ Fire Intensity Gauge</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(gauge_fig, use_container_width=True)
        st.caption(f"Peak FRP recorded: **{max_frp:.1f} MW** | Avg: **{avg_frp:.1f} MW**")

    with col_right:
        # ── Trend mini-charts ───────────────────────────────────────────────
        st.markdown('<div class="section-header">📈 Detection Trends by Year</div>',
                    unsafe_allow_html=True)
        if not trends.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=trends["year"].astype(str), y=trends["fire_count"],
                name="🔥 Fire", marker_color="#FF4757"
            ))
            fig.add_trace(go.Bar(
                x=trends["year"].astype(str), y=trends["flood_count"],
                name="🌊 Flood", marker_color="#1E90FF"
            ))
            fig.add_trace(go.Bar(
                x=trends["year"].astype(str), y=trends["normal_count"],
                name="✅ Normal", marker_color="#2ED573"
            ))
            fig.update_layout(
                barmode="stack",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#0f0f1a",
                font=dict(color="white"),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="white")),
                xaxis=dict(gridcolor="#1e3a5f", title="Year"),
                yaxis=dict(gridcolor="#1e3a5f", title="Detections"),
                margin=dict(t=20, b=40, l=40, r=20),
                height=220,
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Severity Distribution + Event Type ─────────────────────────────────
    col3, col4 = st.columns(2)

    with col3:
        st.markdown('<div class="section-header">🎯 Severity Distribution</div>',
                    unsafe_allow_html=True)
        sev_counts = df["severity"].value_counts()
        fig3 = go.Figure(go.Pie(
            labels=sev_counts.index.tolist(),
            values=sev_counts.values.tolist(),
            hole=0.55,
            marker=dict(colors=["#FF2D2D", "#FFA500", "#2ECC71"],
                        line=dict(color="#0f0f1a", width=2)),
        ))
        fig3.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="white")),
            margin=dict(t=20, b=20, l=20, r=20),
            height=300,
            annotations=[dict(text="Severity", x=0.5, y=0.5,
                              font=dict(size=14, color="white"), showarrow=False)]
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.markdown('<div class="section-header">⚡ Average FRP by Year</div>',
                    unsafe_allow_html=True)
        if not trends.empty:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=trends["year"].astype(str), y=trends["avg_frp"],
                mode="lines+markers+text",
                text=[f"{v:.1f}" for v in trends["avg_frp"]],
                textposition="top center",
                line=dict(color="#FFA502", width=3),
                marker=dict(size=12, color="white", line=dict(color="#FFA502", width=2)),
                fill="tozeroy",
                fillcolor="rgba(255,165,2,0.15)",
                name="Avg FRP (MW)",
            ))
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#0f0f1a",
                font=dict(color="white"),
                xaxis=dict(gridcolor="#1e3a5f", title="Year"),
                yaxis=dict(gridcolor="#1e3a5f", title="Avg FRP (MW)"),
                margin=dict(t=20, b=40, l=40, r=20),
                height=300,
                showlegend=False,
            )
            st.plotly_chart(fig2, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Tab 2 — Interactive Map
# ─────────────────────────────────────────────────────────────────────────────

def render_map_tab(df: pd.DataFrame, max_markers: int):
    st.markdown('<div class="section-header">🗺️ Interactive GIS Disaster Map — India</div>',
                unsafe_allow_html=True)
    st.caption("Color-coded markers: 🔥 Fire | 🌊 Flood | ✅ Normal | 🌡️ Heat Map overlay")

    map_html_path = cfg.MAPS_DIR / "geoshield_map.html"

    with st.spinner("🗺️ Rendering interactive map …"):
        try:
            from src.map_builder import save_map
            save_map(df, path=map_html_path)
        except Exception as e:
            st.error(f"Map build error: {e}")
            return

    try:
        with open(map_html_path, "r", encoding="utf-8") as f:
            map_html = f.read()
        st_components.html(map_html, height=620, scrolling=False)
    except Exception as e:
        st.error(f"Map display error: {e}")
        st.info(f"You can open the map directly: {map_html_path}")

    st.markdown("""
    <div style='background:rgba(0,210,255,0.08); border:1px solid #1e3a5f;
                border-radius:8px; padding:10px 16px; margin-top:8px; font-size:13px;'>
      💡 <b>Tip:</b> Click markers for details · Use scroll to zoom · Toggle layers top-right
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Tab 3 — Analytics
# ─────────────────────────────────────────────────────────────────────────────

def render_analytics(df: pd.DataFrame, trends: pd.DataFrame, charts: list):
    st.markdown('<div class="section-header">📊 Trend Analytics & Reports</div>',
                unsafe_allow_html=True)

    # ── Year-wise Summary Table ────────────────────────────────────────────────
    if not trends.empty:
        st.subheader("📋 Year-wise Summary Table")
        display_trends = trends.copy()
        display_trends["total_area_km2"] = display_trends["total_area_km2"].round(1)
        display_trends["avg_frp"]        = display_trends["avg_frp"].round(2)
        display_trends["avg_confidence"] = display_trends["avg_confidence"].round(1)
        st.dataframe(display_trends, use_container_width=True, hide_index=True)

    # ── Saved chart images — read directly from disk ────────────────────────
    reports_dir = cfg.REPORTS_DIR
    chart_paths = []
    for fname in ["trend_detections.png", "trend_avg_frp.png",
                  "trend_area.png", "trend_high_severity.png"]:
        p = Path(reports_dir) / fname
        if p.exists():
            chart_paths.append(p)

    if chart_paths:
        st.subheader("📈 Generated Charts")
        cols = st.columns(2)
        for i, chart_path in enumerate(chart_paths):
            with cols[i % 2]:
                try:
                    img_bytes = Path(chart_path).read_bytes()
                    st.image(img_bytes, use_container_width=True,
                             caption=Path(chart_path).stem.replace("_", " ").title())
                except Exception as ex:
                    st.warning(f"Could not load chart: {ex}")
    else:
        st.info("📊 Charts will appear here after the first full data load. Please refresh the page.")

    # ── Monthly trend heatmap ──────────────────────────────────────────────────
    st.markdown('<div class="section-header">📅 Monthly Detection Heatmap</div>',
                unsafe_allow_html=True)
    if "month" in df.columns and "year" in df.columns:
        pivot = df.groupby(["year", "month"]).size().reset_index(name="count")
        pivot_wide = pivot.pivot(index="year", columns="month", values="count").fillna(0)
        month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                       "Jul","Aug","Sep","Oct","Nov","Dec"]
        fig = px.imshow(
            pivot_wide,
            labels=dict(x="Month", y="Year", color="Detections"),
            x=[month_names[m-1] for m in pivot_wide.columns],
            y=[str(int(y)) for y in pivot_wide.index],
            color_continuous_scale="YlOrRd",
            aspect="auto",
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f0f1a",
            font=dict(color="white"), margin=dict(t=20, b=40), height=300,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── City-wise Fire Count Chart ─────────────────────────────────────────────
    if "city" in df.columns:
        st.markdown('<div class="section-header">🏙️ Fire Events by City</div>',
                    unsafe_allow_html=True)
        city_fire = (
            df[df["label"] == 1]
            .groupby("city")["frp"]
            .agg(fire_count="count", avg_frp="mean", max_frp="max")
            .reset_index()
            .sort_values("fire_count", ascending=False)
            .head(20)
        )
        fig_city = go.Figure()
        fig_city.add_trace(go.Bar(
            x=city_fire["city"], y=city_fire["fire_count"],
            name="Fire Events",
            marker=dict(color=city_fire["fire_count"],
                        colorscale=[[0,"#FFA502"],[1,"#FF4757"]],
                        showscale=False),
            text=city_fire["fire_count"],
            textposition="outside",
            textfont=dict(color="white", size=10),
        ))
        fig_city.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f0f1a",
            font=dict(color="white"),
            xaxis=dict(gridcolor="#1e3a5f", tickangle=-40, title="City"),
            yaxis=dict(gridcolor="#1e3a5f", title="Fire Detections"),
            margin=dict(t=20, b=120, l=40, r=20), height=400,
        )
        st.plotly_chart(fig_city, use_container_width=True)

        # City-wise avg FRP scatter
        fig_frp = go.Figure(go.Scatter(
            x=city_fire["city"], y=city_fire["avg_frp"],
            mode="markers+text",
            text=[f"{v:.1f}" for v in city_fire["avg_frp"]],
            textposition="top center",
            marker=dict(size=city_fire["fire_count"].apply(lambda x: max(8, min(30, x/2))),
                        color=city_fire["avg_frp"], colorscale="Plasma",
                        showscale=True, colorbar=dict(title="Avg FRP")),
        ))
        fig_frp.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f0f1a",
            font=dict(color="white"),
            xaxis=dict(gridcolor="#1e3a5f", tickangle=-40, title="City"),
            yaxis=dict(gridcolor="#1e3a5f", title="Avg FRP (MW)"),
            title=dict(text="Average Fire Radiative Power per City", font=dict(color="#00d2ff")),
            margin=dict(t=50, b=120, l=40, r=40), height=380,
        )
        st.plotly_chart(fig_frp, use_container_width=True)

    # ── Top 10 Hotspots with City ──────────────────────────────────────────────
    st.markdown('<div class="section-header">🌍 Top 10 Fire Hotspots — India</div>',
                unsafe_allow_html=True)
    _hotspot_cols = ["city", "acq_date", "latitude", "longitude",
                     "frp", "brightness", "confidence", "severity"]
    _hotspot_cols = [c for c in _hotspot_cols if c in df.columns]
    top_spots = (df[df["label"] == 1]
                 .nlargest(10, "frp")
                 [_hotspot_cols]
                 .reset_index(drop=True))
    top_spots.index += 1
    st.dataframe(top_spots, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Tab 4 — AI Prediction
# ─────────────────────────────────────────────────────────────────────────────

def render_prediction():
    st.markdown('<div class="section-header">🤖 AI Event Predictor — Fire & Flood</div>',
                unsafe_allow_html=True)
    st.caption("Enter NASA VIIRS satellite values to predict: 🔥 Fire | 🌊 Flood | ✅ Normal")

    model_loaded, scaler = get_cnn_model()
    model_available = model_loaded is not None

    if not model_available:
        st.info(
            "ℹ️ CNN model not trained yet — using **Smart Rule-Based Engine** that detects "
            "all 3 event types (Fire / Flood / Normal) based on satellite thresholds."
        )

    # ── Preset example buttons ────────────────────────────────────────────────
    st.markdown("**⚡ Load Example Scenario:**")
    p1, p2, p3, p4 = st.columns(4)
    preset = None
    if p1.button("🔥 High Fire",    use_container_width=True): preset = "fire_high"
    if p2.button("🔥 Low Fire",     use_container_width=True): preset = "fire_low"
    if p3.button("🌊 Flood Event",  use_container_width=True): preset = "flood"
    if p4.button("✅ Normal",       use_container_width=True): preset = "normal"

    # Preset values
    PRESETS = {
        "fire_high": dict(brightness=367.0, scan=0.4,  track=0.4,  bright_t31=297.0, frp=133.0, confidence=90),
        "fire_low":  dict(brightness=340.0, scan=0.75, track=0.75, bright_t31=295.0, frp=55.0,  confidence=75),
        "flood":     dict(brightness=298.0, scan=1.2,  track=1.2,  bright_t31=291.0, frp=1.5,   confidence=75),
        "normal":    dict(brightness=312.0, scan=0.75, track=0.75, bright_t31=294.0, frp=3.0,   confidence=75),
    }
    pv = PRESETS.get(preset, PRESETS["normal"])

    with st.form("prediction_form"):
        st.subheader("📡 Satellite Observation Input")
        c1, c2, c3 = st.columns(3)

        with c1:
            brightness = st.number_input("🌡️ Brightness I4 (K)",
                help="Channel I4 ~4µm: Fire pixels are typically >330 K. Flood/water ~295–310 K.",
                value=float(pv["brightness"]), step=1.0, min_value=200.0, max_value=500.0)
            scan = st.number_input("📏 Scan (km)",
                help="Along-scan pixel size. Larger = edge of swath.",
                value=float(pv["scan"]), step=0.05, min_value=0.3, max_value=3.0)
            frp  = st.number_input("⚡ FRP (MW)",
                help="Fire Radiative Power. Fire: >50 MW. Flood/Normal: <10 MW.",
                value=float(pv["frp"]), step=1.0, min_value=0.0, max_value=1000.0)

        with c2:
            track = st.number_input("📏 Track (km)",
                value=float(pv["track"]), step=0.05, min_value=0.3, max_value=3.0)
            bright_t31 = st.number_input("🌡️ Brightness I5 (K)",
                help="Channel I5 ~11µm: Background temp. Flood areas typically 290–300 K.",
                value=float(pv["bright_t31"]), step=1.0, min_value=200.0, max_value=400.0)
            confidence = st.number_input("🎯 Confidence (%)",
                value=int(pv["confidence"]), step=1, min_value=0, max_value=100)

        with c3:
            st.markdown("**📊 Auto-computed Indices**")
            eps  = 1e-5
            ndvi = (bright_t31 - brightness) / (bright_t31 + brightness + eps)
            nbr  = (brightness - frp) / (brightness + frp + eps)
            temp_diff = brightness - bright_t31

            st.metric("🌿 NDVI",      f"{ndvi:.4f}",  help="Vegetation index. Negative = fire/bare.")
            st.metric("🔥 NBR",       f"{nbr:.4f}",   help="Burn Ratio. Low = active fire.")
            st.metric("🌡️ Temp Diff", f"{temp_diff:.1f} K",
                      help="I4 - I5 difference. Fire: >40 K. Flood/Normal: <20 K.")
            st.caption("All indices auto-computed from your inputs.")

        submitted = st.form_submit_button("🚀 Run Prediction", use_container_width=True)

    if submitted:
        row = dict(brightness=brightness, scan=scan, track=track,
                   bright_t31=bright_t31, frp=frp, ndvi=ndvi, nbr=nbr)
        temp_diff = brightness - bright_t31

        if model_available:
            # ── CNN model prediction ──────────────────────────────────────────
            with st.spinner("Running CNN inference …"):
                from src.model_cnn import predict_single
                result = predict_single(row)
            label = result["label_name"]
            conf  = result["confidence"]
            probs = result["probabilities"]
        else:
            # ── Smart Rule-Based Engine (Fire + Flood + Normal) ───────────────
            # Score each class
            fire_score  = 0.0
            flood_score = 0.0
            norm_score  = 0.0

            # Fire signals
            if frp >= cfg.FIRE_FRP_THRESHOLD:         fire_score  += 50
            elif frp >= 20:                            fire_score  += 25
            if brightness >= 360:                      fire_score  += 25
            elif brightness >= 340:                    fire_score  += 15
            if temp_diff >= 40:                        fire_score  += 20
            elif temp_diff >= 20:                      fire_score  += 10
            if nbr < 0.8:                              fire_score  +=  5

            # Flood signals
            if frp <= cfg.FLOOD_FRP_THRESHOLD:         flood_score += 40
            elif frp <= 10:                            flood_score += 20
            if brightness <= 310:                      flood_score += 30
            elif brightness <= 320:                    flood_score += 15
            if temp_diff <= 10:                        flood_score += 20
            elif temp_diff <= 15:                      flood_score += 10
            if bright_t31 <= 295:                      flood_score += 10

            # Normal signals
            if 10 < frp < 50:                          norm_score  += 30
            if 310 < brightness < 345:                 norm_score  += 30
            if 10 < temp_diff < 30:                    norm_score  += 20
            if confidence >= 75:                       norm_score  += 10

            total = fire_score + flood_score + norm_score + 1e-5
            fire_pct  = round(fire_score  / total * 100, 1)
            flood_pct = round(flood_score / total * 100, 1)
            norm_pct  = round(100 - fire_pct - flood_pct, 1)

            if fire_score >= flood_score and fire_score >= norm_score:
                label = "Fire"
            elif flood_score >= fire_score and flood_score >= norm_score:
                label = "Flood"
            else:
                label = "Normal"

            conf  = max(fire_pct, flood_pct, norm_pct)
            probs = {"Fire": fire_pct, "Flood": flood_pct, "Normal": norm_pct}

        # ── Result Card ───────────────────────────────────────────────────────
        emoji = "🔥" if label == "Fire" else "🌊" if label == "Flood" else "✅"
        color = "#FF4757" if label == "Fire" else "#1E90FF" if label == "Flood" else "#2ED573"
        desc  = {
            "Fire":   "High temperature & FRP detected. Active fire event likely.",
            "Flood":  "Low FRP, cool surface. Water/flood conditions detected.",
            "Normal": "Moderate values. No significant fire or flood signature.",
        }[label]

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#0f0f1a,#16213e);
                    border:2px solid {color}; border-radius:16px;
                    padding:24px; text-align:center; margin-top:16px;">
          <div style="font-size:56px; margin-bottom:8px;">{emoji}</div>
          <h2 style="color:{color}; margin:0; font-size:28px; letter-spacing:2px;">
            {label.upper()} DETECTED
          </h2>
          <p style="color:white; font-size:17px; margin:8px 0;">
            Confidence: <b style="color:{color};">{conf:.1f}%</b>
          </p>
          <p style="color:#aaa; font-size:13px; margin:4px 0;">{desc}</p>
          <p style="color:#555; font-size:11px; margin:4px 0;">
            {'🤖 CNN Model' if model_available else '📐 Rule-Based Engine'}
          </p>
        </div>
        """, unsafe_allow_html=True)

        # ── Probability bars for ALL 3 classes ───────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📊 Event Probability Breakdown")
        bar_data = [
            ("🔥 Fire",   probs.get("Fire",   0), "#FF4757"),
            ("🌊 Flood",  probs.get("Flood",  0), "#1E90FF"),
            ("✅ Normal", probs.get("Normal", 0), "#2ED573"),
        ]
        for name, p, bar_color in bar_data:
            st.markdown(f"""
            <div style="margin-bottom:14px;">
              <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span style="color:#ccc; font-size:14px;">{name}</span>
                <span style="color:{bar_color}; font-weight:bold; font-size:14px;">{p:.1f}%</span>
              </div>
              <div style="background:#1a1a2e; border-radius:8px; height:14px; overflow:hidden;">
                <div style="width:{min(p,100):.1f}%; background:linear-gradient(90deg,{bar_color}88,{bar_color});
                            height:100%; border-radius:8px;
                            box-shadow:0 0 8px {bar_color}66;"
                ></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Input summary card ────────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("📋 Input Summary")
        summary_cols = st.columns(4)
        summary_cols[0].metric("🌡️ Brightness", f"{brightness:.1f} K")
        summary_cols[1].metric("⚡ FRP",         f"{frp:.1f} MW")
        summary_cols[2].metric("🌡️ Temp Diff",  f"{temp_diff:.1f} K")
        summary_cols[3].metric("🎯 Confidence", f"{confidence}%")

        # ── Threshold guide ───────────────────────────────────────────────────
        with st.expander("📖 How are predictions made?"):
            st.markdown(f"""
            | Signal | 🔥 Fire | 🌊 Flood | ✅ Normal |
            |--------|---------|---------|----------|
            | **FRP (MW)** | > {cfg.FIRE_FRP_THRESHOLD} | < {cfg.FLOOD_FRP_THRESHOLD} | 10–50 |
            | **Brightness I4 (K)** | > 340 | < 315 | 315–340 |
            | **Temp Diff I4−I5 (K)** | > 40 | < 10 | 10–30 |
            | **NBR** | < 0.8 | Any | Any |

            The **Smart Rule Engine** scores each class independently based on how strongly your
            input values match known satellite signatures, then normalises to 100% probability.
            """)

    # CSV Upload section
    st.markdown("---")
    st.markdown('<div class="section-header">📁 Batch Prediction from CSV</div>',
                unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "Upload a VIIRS CSV file for bulk prediction",
        type=["csv"],
        help="File must have VIIRS column headers"
    )

    if uploaded is not None:
        try:
            up_df = pd.read_csv(uploaded)
            up_df.columns = up_df.columns.str.strip().str.lower()

            # ── Map real NASA FIRMS column names ────────────────────────────
            if "bright_ti4" in up_df.columns:
                up_df = up_df.rename(columns={"bright_ti4": "brightness",
                                              "bright_ti5": "bright_t31"})

            # ── Decode confidence string → numeric ──────────────────────────
            if "confidence" in up_df.columns and up_df["confidence"].dtype == object:
                up_df["confidence_label"] = up_df["confidence"].str.strip().str.lower()
                up_df["confidence"] = up_df["confidence_label"].map(
                    cfg.CONFIDENCE_DECODE).fillna(75).astype(float)
                conf_desc = {
                    "h": "High (≥90%)", "n": "Nominal (75%)", "l": "Low (33%)"
                }
                up_df["confidence_desc"] = up_df["confidence_label"].map(
                    conf_desc).fillna("Unknown")

            # ── Assign nearest city ─────────────────────────────────────────
            if "latitude" in up_df.columns and "longitude" in up_df.columns:
                import numpy as _np
                _cities = {k: v for k, v in cfg.INDIA_CITIES.items() if v is not None}
                _cnames = list(_cities.keys())
                _clats  = _np.array([v[0] for v in _cities.values()])
                _clons  = _np.array([v[1] for v in _cities.values()])
                _lats = pd.to_numeric(up_df["latitude"],  errors="coerce").values
                _lons = pd.to_numeric(up_df["longitude"], errors="coerce").values
                _ld = (_lats[:, None] - _clats[None, :]) ** 2
                _od = (_lons[:, None] - _clons[None, :]) ** 2
                _idx = _np.nanargmin(_ld + _od, axis=1)
                up_df["city"] = [_cnames[i] for i in _idx]

            st.success(f"✅ Loaded {len(up_df):,} rows from `{uploaded.name}`")

            # ── Preview with key columns ─────────────────────────────────────
            _preview_cols = [c for c in
                ["city", "acq_date", "latitude", "longitude",
                 "brightness", "frp", "confidence", "confidence_desc", "daynight"]
                if c in up_df.columns]
            st.dataframe(up_df[_preview_cols].head(20), use_container_width=True)

            # ── Confidence breakdown ─────────────────────────────────────────
            if "confidence_desc" in up_df.columns:
                conf_counts = up_df["confidence_desc"].value_counts().reset_index()
                conf_counts.columns = ["Confidence Level", "Count"]
                fig_conf = go.Figure(go.Pie(
                    labels=conf_counts["Confidence Level"],
                    values=conf_counts["Count"],
                    hole=0.5,
                    marker=dict(colors=["#2ED573","#FFA502","#FF4757"],
                                line=dict(color="#0f0f1a", width=2))
                ))
                fig_conf.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", font=dict(color="white"),
                    legend=dict(bgcolor="rgba(0,0,0,0)"),
                    margin=dict(t=20,b=20,l=20,r=20), height=260,
                    title=dict(text="Confidence Distribution", font=dict(color="#00d2ff"))
                )
                c_conf, c_city = st.columns(2)
                with c_conf:
                    st.plotly_chart(fig_conf, use_container_width=True)
                with c_city:
                    if "city" in up_df.columns:
                        city_counts_up = up_df["city"].value_counts().head(10).reset_index()
                        city_counts_up.columns = ["City", "Records"]
                        fig_city_up = go.Figure(go.Bar(
                            x=city_counts_up["City"], y=city_counts_up["Records"],
                            marker_color="#00d2ff",
                            text=city_counts_up["Records"], textposition="outside",
                            textfont=dict(color="white", size=10),
                        ))
                        fig_city_up.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f0f1a",
                            font=dict(color="white"),
                            xaxis=dict(tickangle=-35),
                            margin=dict(t=20,b=80,l=20,r=20), height=260,
                            title=dict(text="Records by City", font=dict(color="#00d2ff")),
                        )
                        st.plotly_chart(fig_city_up, use_container_width=True)

            if model_available:
                from src.model_cnn import batch_predict
                from src.data_loader import _add_features
                if "acq_date" in up_df.columns:
                    up_df["acq_date"] = pd.to_datetime(up_df["acq_date"], errors="coerce")
                else:
                    up_df["acq_date"] = pd.Timestamp.now()
                for col in ["brightness", "scan", "track", "bright_t31", "frp", "confidence"]:
                    if col not in up_df.columns:
                        up_df[col] = 0.0
                    up_df[col] = pd.to_numeric(up_df[col], errors="coerce").fillna(0)
                up_df = _add_features(up_df)
                preds = batch_predict(up_df)
                lbl_map = {0: "Normal", 1: "Fire", 2: "Flood"}
                up_df["prediction"] = [lbl_map.get(p, "Unknown") for p in preds]
                st.subheader("Batch Prediction Results")
                st.dataframe(up_df[["latitude","longitude","frp","confidence","prediction"]],
                             use_container_width=True)
                csv_out = up_df.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download Predictions CSV", csv_out,
                                   "predictions.csv", "text/csv")
        except Exception as e:
            st.error(f"Error processing file: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Tab 5 — Alerts
# ─────────────────────────────────────────────────────────────────────────────

def render_alerts(df: pd.DataFrame):
    st.markdown('<div class="section-header">🚨 Real-Time Alert System</div>',
                unsafe_allow_html=True)

    stats = get_alert_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📬 Total Alerts",   stats.get("total", 0))
    c2.metric("🔴 High Severity",  stats.get("high",  0))
    c3.metric("🔥 Fire Alerts",    stats.get("fire",  0))
    c4.metric("🌊 Flood Alerts",   stats.get("flood", 0))

    st.markdown("---")

    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.subheader("🚨 Live Alert Processing")
        if st.button("⚡ Scan & Log High-Confidence Alerts", use_container_width=True):
            with st.spinner("Scanning for high-confidence events …"):
                from src.alert_system import process_alerts
                alert_df, count = process_alerts(df, send_notifications=False)

            if count > 0:
                st.toast(f"🚨 {count} alerts logged!", icon="🚨")
                st.success(f"✅ Logged **{count}** alert(s) to database.")
            else:
                st.info("No new high-confidence events found.")

    with col_b:
        st.subheader("⚙️ Alert Config")
        st.metric("Threshold", f"Confidence > {cfg.ALERT_CONFIDENCE_THRESHOLD}%")
        email_status = "✅ Configured" if cfg.SMTP_USER != "your_email@gmail.com" else "❌ Not Set"
        sms_status   = "✅ Configured" if cfg.TWILIO_SID else "❌ Not Set"
        st.caption(f"Email: {email_status}")
        st.caption(f"SMS: {sms_status}")

    st.markdown('<div class="section-header">📋 Alert Log History</div>',
                unsafe_allow_html=True)
    alerts_df = get_all_alerts(limit=200)
    if alerts_df.empty:
        st.info("No alerts logged yet. Click **Scan** above to process alerts.")
    else:
        def highlight_severity(row):
            c = "background-color: rgba(255,45,45,0.2)" if row.get("severity") == "High" \
                else "background-color: rgba(255,165,0,0.15)" if row.get("severity") == "Medium" \
                else ""
            return [c] * len(row)

        styled = alerts_df.style.apply(highlight_severity, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)

        csv_alerts = alerts_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Export Alert Log CSV", csv_alerts,
                           "geoshield_alerts.csv", "text/csv")

    high_events = df[(df["severity"] == "High") & (df["confidence"] > cfg.ALERT_CONFIDENCE_THRESHOLD)]
    if not high_events.empty:
        st.markdown("### 🔴 Active High-Severity Events")
        for _, row in high_events.head(5).iterrows():
            lbl = {0: "Normal", 1: "Fire", 2: "Flood"}.get(int(row.get("label", 0)), "Unknown")
            emoji = "🔥" if lbl=="Fire" else "🌊" if lbl=="Flood" else "⚠️"
            city_str = f" | City: {row.get('city','')}" if "city" in row and row.get("city","") != "Other" else ""
            st.warning(
                f"{emoji} **{lbl}** | "
                f"Lat: {row.get('latitude',0):.3f}, Lon: {row.get('longitude',0):.3f} | "
                f"FRP: {row.get('frp',0):.0f} MW | "
                f"Confidence: {row.get('confidence',0):.0f}% | "
                f"Date: {str(row.get('acq_date',''))[:10]}{city_str}",
                icon="🚨"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tab 6 — Data Explorer
# ─────────────────────────────────────────────────────────────────────────────

def render_data_explorer(df: pd.DataFrame):
    st.markdown('<div class="section-header">🔎 Raw Data Explorer</div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Rows", f"{len(df):,}")
        st.metric("Columns",    len(df.columns))
    with col2:
        st.metric("Fire rows",  f"{(df['label']==1).sum():,}")
        st.metric("Flood rows", f"{(df['label']==2).sum():,}")

    st.subheader("📊 Statistical Summary")
    num_cols = ["brightness", "frp", "confidence", "bright_t31", "ndvi", "nbr", "area_km2"]
    num_cols = [c for c in num_cols if c in df.columns]
    st.dataframe(df[num_cols].describe().round(3), use_container_width=True)

    st.subheader("📋 Sample Data")
    n_show = st.slider("Rows to display", 10, 500, 50, step=10)
    default_cols = ["latitude","longitude","brightness","frp","confidence",
                    "acq_date","label","severity","area_km2"]
    if "city" in df.columns:
        default_cols.insert(4, "city")
    cols_show = st.multiselect(
        "Select columns",
        options=df.columns.tolist(),
        default=[c for c in default_cols if c in df.columns],
    )
    if cols_show:
        st.dataframe(df[cols_show].head(n_show), use_container_width=True, hide_index=True)

    st.markdown("---")
    if st.button("📥 Download Full Cleaned Dataset"):
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download CSV", csv, "geoshield_cleaned.csv", "text/csv")


# ─────────────────────────────────────────────────────────────────────────────
# Tab 7 — City Records (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def render_city_records(df_full: pd.DataFrame, sidebar_city: str):
    st.markdown('<div class="section-header">🏙️ City-Level Fire Records — India</div>',
                unsafe_allow_html=True)
    st.caption("Search fire detection records by Indian city. Uses real NASA VIIRS satellite data.")

    # ── City & Radius Selection ───────────────────────────────────────────────
    col_city, col_rad, col_year = st.columns([2, 1, 1])

    with col_city:
        city_list = list(cfg.INDIA_CITIES.keys())
        default_idx = city_list.index(sidebar_city) if sidebar_city in city_list else 0
        selected_city = st.selectbox(
            "🏙️ Select City",
            options=city_list,
            index=default_idx,
            key="city_tab_select",
        )
    with col_rad:
        radius_km = st.slider("📍 Radius (km)", 10, 150, 60, step=10,
                               help="Search radius around city center")
    with col_year:
        year_filter = st.multiselect("📅 Year", [2022, 2023, 2024],
                                      default=[2022, 2023, 2024], key="city_year")

    # ── Filter by city ────────────────────────────────────────────────────────
    city_df = _filter_city(df_full, selected_city, radius_km)

    if year_filter:
        city_df = city_df[city_df["year"].isin(year_filter)]

    # ── City Info Card ────────────────────────────────────────────────────────
    if selected_city != "All India" and cfg.INDIA_CITIES.get(selected_city):
        clat, clon, _ = cfg.INDIA_CITIES[selected_city]
        fire_ct  = int((city_df["label"] == 1).sum()) if not city_df.empty else 0
        flood_ct = int((city_df["label"] == 2).sum()) if not city_df.empty else 0
        high_ct  = int((city_df["severity"] == "High").sum()) if not city_df.empty else 0
        max_frp  = float(city_df["frp"].max()) if not city_df.empty else 0

        st.markdown(f"""
        <div class="city-card">
          <h3 style="color:#00d2ff; margin:0 0 8px 0;">📍 {selected_city}</h3>
          <div style="display:flex; gap:20px; flex-wrap:wrap;">
            <span style="color:#aaa;">🌐 Lat: <b style="color:white;">{clat:.4f}</b></span>
            <span style="color:#aaa;">🌐 Lon: <b style="color:white;">{clon:.4f}</b></span>
            <span style="color:#aaa;">📍 Radius: <b style="color:white;">{radius_km} km</b></span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if city_df.empty:
            st.warning(f"⚠️ No fire/flood records found within {radius_km} km of **{selected_city}** "
                       f"for the selected years. Try increasing the radius or selecting more years.")
            # Show nearby detections hint
            broader = _filter_city(df_full, selected_city, 200)
            if not broader.empty:
                st.info(f"💡 There are **{len(broader):,}** records within 200 km of {selected_city}. "
                        f"Try increasing the radius slider.")
            return

        # ── City KPI Row ──────────────────────────────────────────────────────
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("📊 Total Records",  f"{len(city_df):,}")
        k2.metric("🔥 Fire Events",    f"{fire_ct:,}")
        k3.metric("🌊 Flood Events",   f"{flood_ct:,}")
        k4.metric("🔴 High Severity",  f"{high_ct:,}")
        k5.metric("⚡ Max FRP",         f"{max_frp:.1f} MW")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── City Map ──────────────────────────────────────────────────────────
        col_map, col_chart = st.columns([1.2, 1])

        with col_map:
            st.markdown('<div class="section-header">🗺️ City Fire Map</div>',
                        unsafe_allow_html=True)
            try:
                city_map = folium.Map(
                    location=[clat, clon],
                    zoom_start=9,
                    tiles="CartoDB dark_matter",
                )
                # Add city center marker
                folium.Marker(
                    [clat, clon],
                    popup=f"📍 {selected_city} City Center",
                    icon=folium.Icon(color="blue", icon="star", prefix="fa"),
                ).add_to(city_map)

                # Add radius circle
                folium.Circle(
                    [clat, clon],
                    radius=radius_km * 1000,
                    color="#00d2ff",
                    fill=True,
                    fill_opacity=0.05,
                    weight=1,
                ).add_to(city_map)

                # Add fire markers (limit to 500)
                plot_df = city_df.head(500)
                for _, row in plot_df.iterrows():
                    lbl = int(row.get("label", 0))
                    frp_val = float(row.get("frp", 0))
                    color = "#FF4757" if lbl == 1 else "#1E90FF" if lbl == 2 else "#2ED573"
                    icon_name = "fire" if lbl == 1 else "tint" if lbl == 2 else "check"
                    folium.CircleMarker(
                        location=[row["latitude"], row["longitude"]],
                        radius=max(3, min(12, frp_val / 20)),
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.7,
                        popup=folium.Popup(
                            f"<b>{'🔥 Fire' if lbl==1 else '🌊 Flood' if lbl==2 else '✅ Normal'}</b><br>"
                            f"Date: {str(row.get('acq_date',''))[:10]}<br>"
                            f"FRP: {frp_val:.1f} MW<br>"
                            f"Brightness: {row.get('brightness',0):.1f} K<br>"
                            f"Confidence: {row.get('confidence',0):.0f}%<br>"
                            f"Severity: {row.get('severity','')}",
                            max_width=200,
                        ),
                    ).add_to(city_map)

                city_map_html = city_map._repr_html_()
                st_components.html(city_map_html, height=420, scrolling=False)
            except Exception as e:
                st.error(f"City map error: {e}")

        with col_chart:
            st.markdown('<div class="section-header">📅 Monthly Fire Activity</div>',
                        unsafe_allow_html=True)
            if "month" in city_df.columns:
                month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                               "Jul","Aug","Sep","Oct","Nov","Dec"]
                monthly = (
                    city_df[city_df["label"] == 1]
                    .groupby("month")
                    .size()
                    .reindex(range(1, 13), fill_value=0)
                    .reset_index()
                )
                monthly.columns = ["month", "count"]
                monthly["month_name"] = monthly["month"].apply(lambda m: month_names[m-1])

                fig_monthly = go.Figure(go.Bar(
                    x=monthly["month_name"],
                    y=monthly["count"],
                    marker=dict(
                        color=monthly["count"],
                        colorscale=[[0, "#2ED573"], [0.5, "#FFA502"], [1, "#FF4757"]],
                        showscale=False,
                    ),
                    text=monthly["count"],
                    textposition="outside",
                    textfont=dict(color="white", size=10),
                ))
                fig_monthly.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="#0f0f1a",
                    font=dict(color="white"),
                    xaxis=dict(gridcolor="#1e3a5f"),
                    yaxis=dict(gridcolor="#1e3a5f", title="Fire Detections"),
                    margin=dict(t=10, b=30, l=40, r=20),
                    height=200,
                )
                st.plotly_chart(fig_monthly, use_container_width=True)

            # Year breakdown
            st.markdown('<div class="section-header">📆 Year-wise Breakdown</div>',
                        unsafe_allow_html=True)
            if "year" in city_df.columns:
                year_data = city_df.groupby("year").agg(
                    total=("frp", "count"),
                    fires=("label", lambda x: (x == 1).sum()),
                    avg_frp=("frp", "mean"),
                    max_frp=("frp", "max"),
                ).reset_index()
                year_data["avg_frp"] = year_data["avg_frp"].round(2)
                year_data["max_frp"] = year_data["max_frp"].round(2)
                st.dataframe(year_data, use_container_width=True, hide_index=True)

        # ── Detailed Records Table ────────────────────────────────────────────
        st.markdown('<div class="section-header">📋 Detailed Fire Records</div>',
                    unsafe_allow_html=True)

        # Filters for table
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            show_type = st.selectbox(
                "Event Type", ["All", "Fire 🔥", "Flood 🌊", "Normal ✅"],
                key="city_event_type"
            )
        with fc2:
            sort_by = st.selectbox(
                "Sort by", ["acq_date (latest)", "frp (highest)", "brightness (highest)"],
                key="city_sort"
            )
        with fc3:
            n_records = st.slider("Show records", 20, 500, 100, step=20, key="city_n_records")

        table_df = city_df.copy()

        # Apply type filter
        type_map = {"Fire 🔥": 1, "Flood 🌊": 2, "Normal ✅": 0}
        if show_type != "All":
            table_df = table_df[table_df["label"] == type_map[show_type]]

        # Apply sort
        if "frp" in sort_by:
            table_df = table_df.nlargest(n_records, "frp")
        elif "brightness" in sort_by:
            table_df = table_df.nlargest(n_records, "brightness")
        else:
            table_df = table_df.sort_values("acq_date", ascending=False).head(n_records)

        # Display columns
        display_cols = ["acq_date", "latitude", "longitude", "brightness", "frp",
                        "confidence", "severity", "label", "daynight"]
        display_cols = [c for c in display_cols if c in table_df.columns]

        label_name_map = {0: "Normal", 1: "Fire", 2: "Flood"}
        table_df["event_type"] = table_df["label"].map(label_name_map)
        display_cols_final = [c for c in display_cols if c != "label"] + ["event_type"]
        display_cols_final = [c for c in display_cols_final if c in table_df.columns]

        st.dataframe(
            table_df[display_cols_final].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )

        # Download city data
        csv_city = city_df.to_csv(index=False).encode("utf-8")
        city_fname = selected_city.replace(" ", "_").replace("/", "_")
        st.download_button(
            f"⬇️ Download {selected_city} Records CSV",
            csv_city,
            f"geoshield_{city_fname}_records.csv",
            "text/csv",
        )

    else:
        # All India selected
        st.info("👆 Select a specific city from the dropdown above to view its records.")
        # Show city summary table
        if "city" in df_full.columns:
            st.markdown('<div class="section-header">🗺️ All Cities Summary</div>',
                        unsafe_allow_html=True)
            city_summary = (
                df_full[df_full["city"] != "Other"]
                .groupby("city")
                .agg(
                    total_records=("frp", "count"),
                    fire_events=("label", lambda x: (x == 1).sum()),
                    avg_frp=("frp", "mean"),
                    max_frp=("frp", "max"),
                    high_severity=("severity", lambda x: (x == "High").sum()),
                )
                .reset_index()
                .sort_values("fire_events", ascending=False)
            )
            city_summary["avg_frp"] = city_summary["avg_frp"].round(2)
            city_summary["max_frp"] = city_summary["max_frp"].round(2)
            st.dataframe(city_summary, use_container_width=True, hide_index=True)

            # Bar chart of cities by fire events
            if not city_summary.empty:
                fig_cities = go.Figure(go.Bar(
                    x=city_summary["city"],
                    y=city_summary["fire_events"],
                    marker=dict(color="#FF4757"),
                    text=city_summary["fire_events"],
                    textposition="outside",
                ))
                fig_cities.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="#0f0f1a",
                    font=dict(color="white"),
                    xaxis=dict(gridcolor="#1e3a5f", tickangle=-45),
                    yaxis=dict(gridcolor="#1e3a5f", title="Fire Events"),
                    margin=dict(t=20, b=100, l=40, r=20),
                    height=350,
                )
                st.plotly_chart(fig_cities, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main App
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # ── Load Data ─────────────────────────────────────────────────────────
    with st.spinner("⏳ Loading real India satellite data (NASA VIIRS JPSS-1) …"):
        try:
            df_full, trends, charts = get_data()
        except Exception as e:
            st.error(f"❌ Data loading failed: {e}")
            st.stop()

    # Ensure category columns are strings on the full df too (for ticker/sidebar)
    for _col in ["severity", "city", "satellite", "daynight"]:
        if _col in df_full.columns and hasattr(df_full[_col], "cat"):
            df_full[_col] = df_full[_col].astype(str)

    filters = render_sidebar(df_full)
    selected_years, selected_labels, selected_severity, conf_min, max_markers, selected_city = filters

    # ── Apply Filters ─────────────────────────────────────────────────────────
    label_id_map = {"Fire": 1, "Flood": 2, "Normal": 0}
    selected_label_ids = [label_id_map[l] for l in selected_labels]

    # Build boolean mask — memory efficient, no full copy
    mask = pd.Series(True, index=df_full.index)
    if selected_years:
        mask &= df_full["year"].isin(selected_years)
    if selected_label_ids:
        mask &= df_full["label"].isin(selected_label_ids)
    if "severity" in df_full.columns and selected_severity:
        # Convert category to string before .isin() to avoid category dtype bugs
        mask &= df_full["severity"].astype(str).isin(selected_severity)
    mask &= df_full["confidence"] >= conf_min

    # Use .copy() only on the filtered subset (much smaller than full df)
    # This avoids SettingWithCopyWarning and category dtype bugs in plotly
    df = df_full.loc[mask].copy()

    # Ensure category columns are strings for plotly compatibility
    for _cat_col in ["severity", "city", "satellite", "daynight"]:
        if _cat_col in df.columns and hasattr(df[_cat_col], "cat"):
            df[_cat_col] = df[_cat_col].astype(str)

    if df.empty:
        st.warning("⚠️ No data matches your current filters. Adjust the sidebar settings.")
        st.stop()

    # ── Tabs ──────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "🏠 Overview",
        "🗺️ Live Map",
        "📊 Analytics",
        "🤖 AI Predict",
        "🚨 Alerts",
        "🔎 Data Explorer",
        "🏙️ City Records",
    ])

    with tabs[0]: render_overview(df, trends)
    with tabs[1]: render_map_tab(df, max_markers)
    with tabs[2]: render_analytics(df, trends, charts)
    with tabs[3]: render_prediction()
    with tabs[4]: render_alerts(df)
    with tabs[5]: render_data_explorer(df)
    with tabs[6]: render_city_records(df_full, selected_city)


if __name__ == "__main__":
    main()
