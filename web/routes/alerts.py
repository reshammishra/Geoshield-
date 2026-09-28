"""GeoShield – Alerts blueprint (rules, CRUD, acknowledge, resolve)"""
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from flask import (Blueprint, render_template, jsonify, request, session)
from routes.auth import login_required

alerts_bp = Blueprint("alerts", __name__)
log = logging.getLogger("GeoShield.Alerts")

ROOT    = Path(__file__).parent.parent.parent
DB_PATH = ROOT / "alerts" / "alerts.db"


def _init_alerts_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            acq_date    TEXT,
            latitude    REAL,
            longitude   REAL,
            label       TEXT,
            severity    TEXT,
            frp         REAL,
            confidence  REAL,
            brightness  REAL,
            area_km2    REAL,
            satellite   TEXT,
            email_sent  INTEGER DEFAULT 0,
            sms_sent    INTEGER DEFAULT 0,
            status      TEXT    DEFAULT 'ACTIVE',
            ack_by      TEXT,
            ack_at      TEXT,
            city        TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            condition   TEXT    NOT NULL,
            threshold   REAL    NOT NULL,
            event_type  TEXT    DEFAULT 'any',
            enabled     INTEGER DEFAULT 1,
            created_by  TEXT,
            created_at  TEXT    DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Seed default rules if empty
    cur = conn.execute("SELECT COUNT(*) FROM alert_rules")
    if cur.fetchone()[0] == 0:
        default_rules = [
            ("High FRP Fire",      "frp",        150.0, "Fire"),
            ("High Risk Score",    "risk_score",  75.0, "any"),
            ("Long Duration Event","duration",     7.0, "any"),
            ("Dense Fire Cluster", "detections",  20.0, "Fire"),
        ]
        conn.executemany(
            "INSERT INTO alert_rules (name, condition, threshold, event_type, created_by) VALUES (?,?,?,?,'system')",
            default_rules
        )
    conn.commit()
    conn.close()


def _conn():
    _init_alerts_db()
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


@alerts_bp.route("/alerts")
@login_required
def alerts_page():
    return render_template("alerts.html", user=session.get("user"))


@alerts_bp.route("/api/alerts")
@login_required
def api_list_alerts():
    try:
        status = request.args.get("status")
        limit  = request.args.get("limit", 200, type=int)
        conn   = _conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE status=? ORDER BY timestamp DESC LIMIT ?",
                (status.upper(), limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return jsonify({"alerts": [dict(r) for r in rows], "total": len(rows)})
    except Exception as e:
        log.exception("list alerts error")
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/api/alerts/stats")
@login_required
def api_alert_stats():
    try:
        conn   = _conn()
        cur    = conn.cursor()
        total  = cur.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        active = cur.execute("SELECT COUNT(*) FROM alerts WHERE status='ACTIVE'").fetchone()[0]
        acked  = cur.execute("SELECT COUNT(*) FROM alerts WHERE status='ACKNOWLEDGED'").fetchone()[0]
        resol  = cur.execute("SELECT COUNT(*) FROM alerts WHERE status='RESOLVED'").fetchone()[0]
        high   = cur.execute("SELECT COUNT(*) FROM alerts WHERE severity='High'").fetchone()[0]
        fire   = cur.execute("SELECT COUNT(*) FROM alerts WHERE label='Fire'").fetchone()[0]
        flood  = cur.execute("SELECT COUNT(*) FROM alerts WHERE label='Flood'").fetchone()[0]
        conn.close()
        return jsonify({
            "total": total, "active": active, "acknowledged": acked,
            "resolved": resol, "high": high, "fire": fire, "flood": flood
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/api/alerts/<int:alert_id>/acknowledge", methods=["POST"])
@login_required
def api_acknowledge(alert_id: int):
    try:
        user = session["user"]["username"]
        conn = _conn()
        conn.execute(
            "UPDATE alerts SET status='ACKNOWLEDGED', ack_by=?, ack_at=? WHERE id=?",
            (user, datetime.utcnow().isoformat(), alert_id)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "alert_id": alert_id, "status": "ACKNOWLEDGED"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/api/alerts/<int:alert_id>/resolve", methods=["POST"])
@login_required
def api_resolve(alert_id: int):
    try:
        user = session["user"]["username"]
        conn = _conn()
        conn.execute(
            "UPDATE alerts SET status='RESOLVED', ack_by=?, ack_at=? WHERE id=?",
            (user, datetime.utcnow().isoformat(), alert_id)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "alert_id": alert_id, "status": "RESOLVED"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@alerts_bp.route("/api/alerts/scan", methods=["POST"])
@login_required
def api_scan_alerts():
    """Scan current incidents against alert rules and log new alerts."""
    try:
        from services.data_service import get_df
        from services.event_fusion import fuse_events
        from src.alert_system import log_alert, init_db

        df  = get_df()
        inc = fuse_events(df, event_type="all")

        conn = _conn()
        rules = conn.execute(
            "SELECT * FROM alert_rules WHERE enabled=1"
        ).fetchall()

        triggered = 0
        for _, row in inc.iterrows():
            for rule in rules:
                rule = dict(rule)
                cond      = rule["condition"]
                threshold = rule["threshold"]
                etype     = rule["event_type"]

                if etype != "any" and str(row.get("event_type","")) != etype:
                    continue

                val = None
                if cond == "frp":
                    val = float(row.get("max_frp", 0))
                elif cond == "risk_score":
                    val = float(row.get("risk_score", 0))
                elif cond == "duration":
                    val = float(row.get("duration_days", 0))
                elif cond == "detections":
                    val = float(row.get("detection_count", 0))

                if val is not None and val >= threshold:
                    conn.execute("""
                        INSERT INTO alerts
                          (timestamp, latitude, longitude, label, severity,
                           frp, confidence, city, status)
                        VALUES (?,?,?,?,?,?,?,?,'ACTIVE')
                    """, (
                        datetime.utcnow().isoformat(),
                        float(row["latitude"]),
                        float(row["longitude"]),
                        str(row["event_type"]),
                        str(row.get("severity","Low")),
                        float(row.get("max_frp",0)),
                        float(row.get("avg_confidence",75)),
                        str(row.get("city","")),
                    ))
                    triggered += 1

        conn.commit()
        conn.close()
        return jsonify({"triggered": triggered, "rules_checked": len(rules)})
    except Exception as e:
        log.exception("scan alerts error")
        return jsonify({"error": str(e)}), 500


# ── Alert Rules CRUD ──────────────────────────────────────────────────────────

@alerts_bp.route("/api/alert-rules")
@login_required
def api_list_rules():
    conn  = _conn()
    rows  = conn.execute("SELECT * FROM alert_rules ORDER BY id").fetchall()
    conn.close()
    return jsonify({"rules": [dict(r) for r in rows]})


@alerts_bp.route("/api/alert-rules", methods=["POST"])
@login_required
def api_create_rule():
    try:
        data = request.get_json()
        conn = _conn()
        conn.execute("""
            INSERT INTO alert_rules (name, condition, threshold, event_type, enabled, created_by)
            VALUES (?,?,?,?,?,?)
        """, (
            data["name"], data["condition"], float(data["threshold"]),
            data.get("event_type","any"), 1,
            session["user"]["username"]
        ))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@alerts_bp.route("/api/alert-rules/<int:rule_id>", methods=["DELETE"])
@login_required
def api_delete_rule(rule_id: int):
    conn = _conn()
    conn.execute("DELETE FROM alert_rules WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@alerts_bp.route("/api/alert-rules/<int:rule_id>/toggle", methods=["POST"])
@login_required
def api_toggle_rule(rule_id: int):
    conn = _conn()
    conn.execute("UPDATE alert_rules SET enabled = 1 - enabled WHERE id=?", (rule_id,))
    conn.commit()
    row  = conn.execute("SELECT enabled FROM alert_rules WHERE id=?", (rule_id,)).fetchone()
    conn.close()
    return jsonify({"enabled": bool(row["enabled"]) if row else False})
