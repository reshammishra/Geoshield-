"""GeoShield – Data routes (Watchlist, Disaster Replay page, Alert Simulator)"""
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, jsonify, request, session
from routes.auth import login_required
from services.data_service import get_df
from services.event_fusion import fuse_events

data_bp = Blueprint("data", __name__)
log = logging.getLogger("GeoShield.DataRoutes")

ROOT = Path(__file__).parent.parent.parent
DB_PATH = ROOT / "alerts" / "geoshield_users.db"


def _init_watchlist_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            location_name TEXT NOT NULL,
            location_type TEXT DEFAULT 'city',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _get_db():
    _init_watchlist_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@data_bp.route("/replay")
@login_required
def replay_page():
    return render_template("replay.html", user=session.get("user"))


@data_bp.route("/watchlist")
@login_required
def watchlist_page():
    return render_template("watchlist.html", user=session.get("user"))


@data_bp.route("/simulator")
@login_required
def simulator_page():
    return render_template("simulator.html", user=session.get("user"))


# ── Watchlist REST API ────────────────────────────────────────────────────────

@data_bp.route("/api/watchlist", methods=["GET"])
@login_required
def api_get_watchlist():
    try:
        user_id = session["user"]["id"]
        conn = _get_db()
        rows = conn.execute(
            "SELECT * FROM watchlist WHERE user_id=? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        conn.close()

        df = get_df()
        watchlist = []
        for r in rows:
            loc = r["location_name"]
            # Compute current stats for location from real data
            sub = df[df["city"].str.lower() == loc.lower()] if "city" in df.columns else df.iloc[0:0]
            fire_count = int((sub["label"] == 1).sum()) if not sub.empty else 0
            flood_count = int((sub["label"] == 2).sum()) if not sub.empty else 0
            high_sev = int((sub["severity"] == "High").sum()) if not sub.empty and "severity" in sub.columns else 0
            max_frp = float(sub["frp"].max()) if not sub.empty and sub["frp"].notna().any() else 0.0

            # Calculate risk
            risk_score = min(100, int((fire_count * 0.5) + (high_sev * 2) + (max_frp * 0.1)))
            risk_level = "CRITICAL" if risk_score > 75 else "HIGH" if risk_score > 50 else "MEDIUM" if risk_score > 25 else "LOW"

            watchlist.append({
                "id": r["id"],
                "location_name": r["location_name"],
                "location_type": r["location_type"],
                "notes": r["notes"],
                "created_at": r["created_at"],
                "active_events": fire_count + flood_count,
                "fire_count": fire_count,
                "flood_count": flood_count,
                "high_severity": high_sev,
                "max_frp": round(max_frp, 1),
                "risk_score": risk_score,
                "risk_level": risk_level,
                "last_update": str(sub["acq_date"].max())[:10] if not sub.empty else "N/A"
            })

        return jsonify({"watchlist": watchlist, "total": len(watchlist)})
    except Exception as e:
        log.exception("watchlist fetch error")
        return jsonify({"error": str(e)}), 500


@data_bp.route("/api/watchlist", methods=["POST"])
@login_required
def api_add_watchlist():
    try:
        user_id = session["user"]["id"]
        data = request.get_json() or {}
        loc = data.get("location_name", "").strip()
        loc_type = data.get("location_type", "city").strip()
        notes = data.get("notes", "").strip()

        if not loc:
            return jsonify({"error": "Location name is required"}), 400

        conn = _get_db()
        cur = conn.execute(
            "INSERT INTO watchlist (user_id, location_name, location_type, notes) VALUES (?, ?, ?, ?)",
            (user_id, loc, loc_type, notes)
        )
        conn.commit()
        item_id = cur.lastrowid
        conn.close()

        return jsonify({"success": True, "id": item_id, "message": f"{loc} added to watchlist."})
    except Exception as e:
        log.exception("add watchlist error")
        return jsonify({"error": str(e)}), 500


@data_bp.route("/api/watchlist/<int:item_id>", methods=["DELETE"])
@login_required
def api_delete_watchlist(item_id: int):
    try:
        user_id = session["user"]["id"]
        conn = _get_db()
        conn.execute("DELETE FROM watchlist WHERE id=? AND user_id=?", (item_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Watchlist item removed."})
    except Exception as e:
        log.exception("delete watchlist error")
        return jsonify({"error": str(e)}), 500


# ── Alert Simulator API (DEMO MODE) ──────────────────────────────────────────

@data_bp.route("/api/simulator/scenarios")
@login_required
def api_simulator_scenarios():
    """Returns top real historical disaster incidents to run simulation on."""
    try:
        df = get_df()
        inc = fuse_events(df, event_type="all")
        # Grab top 10 diverse incidents for demonstration
        top = inc.head(10)
        scenarios = []
        for _, r in top.iterrows():
            scenarios.append({
                "event_id": str(r["event_id"]),
                "event_type": str(r["event_type"]),
                "city": str(r.get("city", "Unknown")),
                "date": str(r["start_time"])[:10],
                "max_frp": float(r["max_frp"]),
                "detection_count": int(r["detection_count"]),
                "duration_days": int(r["duration_days"]),
                "severity": str(r.get("severity", "Low")),
                "risk_score": int(r["risk_score"]),
                "risk_level": str(r["risk_level"])
            })
        return jsonify({"scenarios": scenarios})
    except Exception as e:
        log.exception("simulator scenarios error")
        return jsonify({"error": str(e)}), 500


@data_bp.route("/api/simulator/run", methods=["POST"])
@login_required
def api_simulator_run():
    """Simulates alert pipeline evaluation step-by-step for a chosen incident."""
    try:
        data = request.get_json() or {}
        event_id = data.get("event_id")

        df = get_df()
        inc = fuse_events(df, event_type="all")
        row = inc[inc["event_id"] == event_id]
        if row.empty:
            return jsonify({"error": "Incident scenario not found"}), 404

        r = row.iloc[0]
        # Evaluate step by step
        steps = [
            {
                "step": 1,
                "name": "Satellite Ingestion",
                "status": "COMPLETED",
                "details": f"VIIRS JPSS-1 detected {r['detection_count']} spatial signals near {r.get('city','Unknown')}."
            },
            {
                "step": 2,
                "name": "Data Fusion & Validation",
                "status": "COMPLETED",
                "details": f"Spatial cluster radius 15km grouped {r['detection_count']} detections over {r['duration_days']} active days."
            },
            {
                "step": 3,
                "name": "Dynamic Risk Engine Evaluation",
                "status": "COMPLETED",
                "details": f"Calculated score: {r['risk_score']}/100 ({r['risk_level']}). Primary factor: FRP ({r['max_frp']} MW)."
            },
            {
                "step": 4,
                "name": "Alert Rule Matching",
                "status": "TRIGGERED" if r["risk_score"] >= 50 or r["max_frp"] >= 100 else "MONITORING",
                "details": f"Rule 'High FRP Fire (>100MW)' or 'Risk Score > 50' evaluated. Action: {'TRIGGER EMERGENCY ALERT' if r['risk_score'] >= 50 else 'LOG AS LOW PRIORITY'}."
            },
            {
                "step": 5,
                "name": "Notification Dispatch Simulator",
                "status": "DISPATCHED" if r["risk_score"] >= 50 else "SUPPRESSED",
                "details": f"{'SMS & Email payloads generated and mock dispatched to responders.' if r['risk_score'] >= 50 else 'Threshold not reached. Alert queued in standby.'}"
            }
        ]

        return jsonify({
            "simulation_mode": True,
            "event_id": event_id,
            "incident": {
                "event_type": str(r["event_type"]),
                "city": str(r.get("city", "Unknown")),
                "risk_score": int(r["risk_score"]),
                "risk_level": str(r["risk_level"]),
                "max_frp": float(r["max_frp"]),
                "detections": int(r["detection_count"])
            },
            "steps": steps
        })
    except Exception as e:
        log.exception("simulator run error")
        return jsonify({"error": str(e)}), 500
