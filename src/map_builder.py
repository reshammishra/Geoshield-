"""
GEOSHIELD — Folium Map Builder (Step 4)
Builds an interactive GIS map with:
  • Color-coded severity markers with rich popups
  • HeatLayer for density visualisation
  • Cluster markers per event type
  • Layer controls (Fire / Flood / Normal / Heat)
  • Before/After comparison slider (SideBySideLayers)
"""

import logging
import sys
from pathlib import Path

import folium
import folium.plugins as plugins
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    MAP_CENTER, MAP_ZOOM, MAP_OUTPUT, SEVERITY_COLORS, MAPS_DIR
)

log = logging.getLogger("GeoShield.MapBuilder")
logging.basicConfig(level=logging.INFO,
                    format="[%(asctime)s] %(levelname)s — %(message)s",
                    datefmt="%H:%M:%S")

# Label numeric → string mapping
LABEL_NAMES = {0: "Normal", 1: "Fire", 2: "Flood"}
LABEL_ICONS  = {0: "check-circle", 1: "fire", 2: "tint"}
LABEL_COLORS = {0: "green", 1: "red", 2: "blue"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _severity_icon(row: pd.Series) -> tuple[str, str]:
    """Return (color, icon) for a marker based on label and severity."""
    label_id = int(row.get("label", 0))
    severity = str(row.get("severity", "Low"))

    if label_id == 1:          # Fire
        color = "red" if severity == "High" else "orange" if severity == "Medium" else "lightred"
        icon  = "fire"
    elif label_id == 2:        # Flood
        color = "darkblue" if severity == "High" else "blue" if severity == "Medium" else "lightblue"
        icon  = "tint"
    else:                      # Normal
        color = "green"
        icon  = "leaf"

    return color, icon


def _popup_html(row: pd.Series) -> str:
    """Build styled HTML popup content for a marker."""
    label_id = int(row.get("label", 0))
    severity = str(row.get("severity", "Low"))
    sev_color = SEVERITY_COLORS.get(severity, "#aaaaaa")

    return f"""
    <div style="font-family:Arial,sans-serif; min-width:220px; font-size:13px;">
      <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);
                  padding:10px 14px; border-radius:8px 8px 0 0; border-bottom:2px solid {sev_color};">
        <b style="color:{sev_color}; font-size:15px;">
          {'🔥 FIRE' if label_id==1 else '🌊 FLOOD' if label_id==2 else '✅ NORMAL'}
        </b>
        <span style="float:right; background:{sev_color}; color:#000;
                     padding:2px 8px; border-radius:10px; font-size:11px; font-weight:bold;">
          {severity}
        </span>
      </div>
      <div style="background:#0f0f1a; padding:10px 14px; border-radius:0 0 8px 8px;">
        <table style="width:100%; color:#cccccc; border-collapse:collapse;">
          <tr><td style="padding:3px 0;"><b style="color:#aaa;">📅 Date</b></td>
              <td style="text-align:right;">{str(row.get("acq_date","N/A"))[:10]}</td></tr>
          <tr><td><b style="color:#aaa;">📍 Lat / Lon</b></td>
              <td style="text-align:right;">{row.get("latitude",0):.4f}, {row.get("longitude",0):.4f}</td></tr>
          <tr><td><b style="color:#aaa;">🌡️ Brightness</b></td>
              <td style="text-align:right;">{row.get("brightness",0):.1f} K</td></tr>
          <tr><td><b style="color:#aaa;">⚡ FRP</b></td>
              <td style="text-align:right; color:#FFA502;">{row.get("frp",0):.1f} MW</td></tr>
          <tr><td><b style="color:#aaa;">🎯 Confidence</b></td>
              <td style="text-align:right;">{row.get("confidence",0):.0f}%</td></tr>
          <tr><td><b style="color:#aaa;">📐 Area</b></td>
              <td style="text-align:right;">{row.get("area_km2",0):.2f} km²</td></tr>
          <tr><td><b style="color:#aaa;">🛰️ Satellite</b></td>
              <td style="text-align:right;">{row.get("satellite","JPSS-1")}</td></tr>
          <tr><td><b style="color:#aaa;">⏱️ NDVI</b></td>
              <td style="text-align:right;">{row.get("ndvi",0):.4f}</td></tr>
        </table>
      </div>
    </div>
    """


# ─────────────────────────────────────────────────────────────────────────────
# Map Builder
# ─────────────────────────────────────────────────────────────────────────────

def build_map(df: pd.DataFrame, max_markers: int = 500) -> folium.Map:
    """
    Build interactive Folium map with all layers.

    Parameters
    ----------
    df          : Cleaned + risk-analyzed DataFrame
    max_markers : Cap to avoid browser freeze on huge datasets

    Returns
    -------
    folium.Map
    """
    # Ensure required columns exist
    if "label" not in df.columns:
        df["label"] = 0
    if "severity" not in df.columns:
        df["severity"] = "Low"
    if "area_km2" not in df.columns:
        df["area_km2"] = df.get("scan", 1) * df.get("track", 1)

    # Sample for performance
    if len(df) > max_markers:
        df_sample = df.sample(max_markers, random_state=42)
        log.info(f"Sampled {max_markers} rows from {len(df)} for map rendering.")
    else:
        df_sample = df

    # ── Base Map ─────────────────────────────────────────────────────────────
    m = folium.Map(
        location=MAP_CENTER,
        zoom_start=MAP_ZOOM,
        tiles=None,       # Custom tiles added below
        prefer_canvas=True,
    )

    # Dark base tile
    folium.TileLayer(
        tiles="CartoDB dark_matter",
        name="🌑 Dark (Base)",
        control=True,
    ).add_to(m)

    # Satellite imagery tile
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="ESRI World Imagery",
        name="🛰️ Satellite Imagery",
        control=True,
    ).add_to(m)

    # ── Feature Groups (Layers) ───────────────────────────────────────────────
    fg_fire   = folium.FeatureGroup(name="🔥 Fire Detections",   show=True)
    fg_flood  = folium.FeatureGroup(name="🌊 Flood Detections",  show=True)
    fg_normal = folium.FeatureGroup(name="✅ Normal Detections", show=False)

    # ── Marker Clusters inside each group ────────────────────────────────────
    cluster_fire  = plugins.MarkerCluster(name="Fire Cluster")
    cluster_flood = plugins.MarkerCluster(name="Flood Cluster")

    heat_data = []   # For HeatLayer

    for _, row in df_sample.iterrows():
        lat  = row["latitude"]
        lon  = row["longitude"]
        lbl  = int(row.get("label", 0))
        frp  = float(row.get("frp", 0))

        color, icon_name = _severity_icon(row)
        popup = folium.Popup(folium.IFrame(_popup_html(row), width=260, height=230),
                             max_width=270)
        marker = folium.Marker(
            location=[lat, lon],
            popup=popup,
            tooltip=f"{'🔥' if lbl==1 else '🌊' if lbl==2 else '✅'} {LABEL_NAMES[lbl]} | FRP: {frp:.0f} MW",
            icon=folium.Icon(color=color, icon=icon_name, prefix="fa"),
        )

        if lbl == 1:
            cluster_fire.add_child(marker)
            heat_data.append([lat, lon, min(frp / 500.0, 1.0)])  # normalised
        elif lbl == 2:
            cluster_flood.add_child(marker)
            heat_data.append([lat, lon, 0.5])
        else:
            fg_normal.add_child(marker)

    fg_fire.add_child(cluster_fire)
    fg_flood.add_child(cluster_flood)

    m.add_child(fg_fire)
    m.add_child(fg_flood)
    m.add_child(fg_normal)

    # ── HeatMap Layer ─────────────────────────────────────────────────────────
    if heat_data:
        plugins.HeatMap(
            heat_data,
            name="🌡️ Severity Heat Map",
            min_opacity=0.3,
            max_zoom=10,
            radius=18,
            blur=15,
            gradient={0.2: "blue", 0.5: "lime", 0.8: "orange", 1.0: "red"},
        ).add_to(m)

    # ── MiniMap ──────────────────────────────────────────────────────────────
    plugins.MiniMap(toggle_display=True).add_to(m)

    # ── Fullscreen ────────────────────────────────────────────────────────────
    plugins.Fullscreen(position="topright").add_to(m)

    # ── Locate Control ───────────────────────────────────────────────────────
    plugins.LocateControl(auto_start=False).add_to(m)

    # ── Layer Control ─────────────────────────────────────────────────────────
    folium.LayerControl(collapsed=False).add_to(m)

    # ── Custom Legend ─────────────────────────────────────────────────────────
    legend_html = """
    <div style="position:fixed; bottom:30px; right:30px; z-index:9999;
                background:rgba(15,15,26,0.92); padding:14px 18px;
                border-radius:12px; border:1px solid #333;
                font-family:Arial,sans-serif; color:white; font-size:13px;
                box-shadow:0 4px 20px rgba(0,0,0,0.5);">
      <b style="font-size:14px; color:#00d2ff;">🛡️ GEOSHIELD</b><br><br>
      <span style="color:#FF2D2D;">●</span> <b>High Severity</b><br>
      <span style="color:#FFA500;">●</span> <b>Medium Severity</b><br>
      <span style="color:#2ECC71;">●</span> <b>Low Severity</b><br>
      <hr style="border-color:#333; margin:8px 0;">
      <span>🔥 Fire &nbsp; 🌊 Flood &nbsp; ✅ Normal</span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    log.info(f"Map built with {len(df_sample)} markers.")
    return m


def save_map(df: pd.DataFrame, path: Path = None) -> Path:
    """Build and save the Folium map to HTML."""
    path = path or MAP_OUTPUT
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    m = build_map(df)
    m.save(str(path))
    log.info(f"Map saved → {path}")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from src.data_loader import load_all_data
    from src.risk_analysis import run_risk_analysis

    log.info("=== GEOSHIELD Map Builder ===")
    df = load_all_data(save=False)
    df_risk, _, _ = run_risk_analysis(df)
    out = save_map(df_risk)
    print(f"\n✅ Interactive map saved → {out}")
    print("Open it in your browser to explore!")
