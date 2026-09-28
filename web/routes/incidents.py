"""GeoShield – Incidents routes (event fusion, map data, detail)"""
import logging
import json
import numpy as np
from flask import Blueprint, render_template, jsonify, request, session
from routes.auth import login_required
from services.data_service import get_df, apply_filters
from services.event_fusion import fuse_events, paginate

incidents_bp = Blueprint("incidents", __name__)
log = logging.getLogger("GeoShield.Incidents")

# Cache fused events per session request (in-process, not persistent)
_incident_cache: dict = {}


def _get_incidents(params: dict):
    df = get_df()
    filtered = apply_filters(df, params)
    event_type = params.get("event_type", "all")
    incidents_df = fuse_events(filtered, event_type=event_type)
    return incidents_df


def _safe_float(v):
    if isinstance(v, (np.floating, float)):
        return float(v) if np.isfinite(v) else None
    return v


def _serialize_incident(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if isinstance(v, (np.integer,)):
            out[k] = int(v)
        elif isinstance(v, (np.floating,)):
            out[k] = float(v) if np.isfinite(v) else None
        elif isinstance(v, list):
            out[k] = v
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


@incidents_bp.route("/incidents")
@login_required
def incidents_page():
    return render_template("incidents.html", user=session.get("user"))


@incidents_bp.route("/api/incidents")
@login_required
def api_incidents():
    try:
        params = {
            "years":            request.args.getlist("years") or [],
            "event_types":      request.args.getlist("event_types") or [],
            "severity_levels":  request.args.getlist("severity") or [],
            "confidence_min":   request.args.get("confidence_min", 50, type=float),
            "date_from":        request.args.get("date_from"),
            "date_to":          request.args.get("date_to"),
            "city":             request.args.get("city"),
            "event_type":       request.args.get("event_type", "all"),
        }
        page     = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)

        inc_df = _get_incidents(params)
        result = paginate(inc_df, page=page, per_page=per_page)
        result["incidents"] = [_serialize_incident(r) for r in result["incidents"]]
        return jsonify(result)
    except Exception as e:
        log.exception("incidents error")
        return jsonify({"error": str(e)}), 500


@incidents_bp.route("/api/incidents/map")
@login_required
def api_incidents_map():
    """Return lightweight GeoJSON for map rendering (no risk_factors in response)."""
    try:
        params = {
            "years":          request.args.getlist("years") or [],
            "event_types":    request.args.getlist("event_types") or [],
            "severity_levels":request.args.getlist("severity") or [],
            "confidence_min": request.args.get("confidence_min", 50, type=float),
            "date_from":      request.args.get("date_from"),
            "date_to":        request.args.get("date_to"),
            "event_type":     request.args.get("event_type", "all"),
        }
        max_markers = request.args.get("max_markers", 2000, type=int)

        inc_df = _get_incidents(params)
        if inc_df.empty:
            return jsonify({"type": "FeatureCollection", "features": [], "total": 0})

        # Limit for map performance
        subset = inc_df.head(max_markers)
        features = []
        for _, row in subset.iterrows():
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row["longitude"]), float(row["latitude"])],
                },
                "properties": {
                    "event_id":        str(row["event_id"]),
                    "event_type":      str(row["event_type"]),
                    "city":            str(row.get("city", "")),
                    "risk_score":      int(row["risk_score"]),
                    "risk_level":      str(row["risk_level"]),
                    "severity":        str(row.get("severity", "Low")),
                    "detection_count": int(row["detection_count"]),
                    "max_frp":         float(row["max_frp"]),
                    "duration_days":   int(row["duration_days"]),
                    "start_time":      str(row["start_time"]),
                    "latest_detection":str(row["latest_detection"]),
                    "priority_rank":   int(row["priority_rank"]),
                },
            })

        return jsonify({
            "type":     "FeatureCollection",
            "features": features,
            "total":    int(len(inc_df)),
        })
    except Exception as e:
        log.exception("map incidents error")
        return jsonify({"error": str(e)}), 500


@incidents_bp.route("/api/incidents/<incident_id>")
@login_required
def api_incident_detail(incident_id: str):
    """Return full incident details including risk factor breakdown and evidence."""
    try:
        params = {"event_type": "all"}
        inc_df = _get_incidents(params)

        row = inc_df[inc_df["event_id"] == incident_id]
        if row.empty:
            return jsonify({"error": f"Incident {incident_id} not found"}), 404

        row = row.iloc[0]
        detail = _serialize_incident(row.to_dict())

        # Fetch the raw detections that make up this incident (for evidence tab)
        df = get_df()
        # Find detections near this incident's location + time
        lat, lon = float(row["latitude"]), float(row["longitude"])
        from datetime import datetime, timedelta
        try:
            start_dt = datetime.fromisoformat(str(row["start_time"]).replace("T"," ").split(".")[0])
            end_dt   = datetime.fromisoformat(str(row["latest_detection"]).replace("T"," ").split(".")[0])
        except Exception:
            start_dt = df["acq_date"].min()
            end_dt   = df["acq_date"].max()

        # Spatial + temporal window for evidence
        deg = 0.15  # ~17 km
        evidence = df[
            (df["latitude"].between(lat - deg, lat + deg)) &
            (df["longitude"].between(lon - deg, lon + deg)) &
            (df["acq_date"] >= start_dt) &
            (df["acq_date"] <= end_dt + timedelta(days=1))
        ].head(100)

        evidence_cols = ["acq_date","latitude","longitude","brightness",
                         "frp","confidence","label","city"]
        if "severity" in evidence.columns:
            evidence_cols.append("severity")
        evidence_records = []
        for _, er in evidence[evidence_cols].iterrows():
            rec = {}
            for k, v in er.items():
                if hasattr(v, "isoformat"):
                    rec[k] = str(v)[:10]
                elif isinstance(v, (np.integer,)):
                    rec[k] = int(v)
                elif isinstance(v, (np.floating,)):
                    rec[k] = round(float(v), 4) if np.isfinite(v) else None
                else:
                    rec[k] = v
            rec["event_type"] = {0:"Normal",1:"Fire",2:"Flood"}.get(rec.get("label",0),"Unknown")
            evidence_records.append(rec)

        detail["evidence"] = evidence_records
        detail["evidence_count"] = len(evidence_records)
        return jsonify(detail)

    except Exception as e:
        log.exception("incident detail error")
        return jsonify({"error": str(e)}), 500


@incidents_bp.route("/api/incidents/priority")
@login_required
def api_priority_queue():
    """Return top-N incidents sorted by risk score (priority queue)."""
    try:
        n = request.args.get("n", 20, type=int)
        filter_level  = request.args.get("risk_level")
        filter_type   = request.args.get("event_type", "all")
        min_duration  = request.args.get("min_duration", 0, type=int)

        params = {"event_type": filter_type}
        inc_df = _get_incidents(params)

        if filter_level:
            inc_df = inc_df[inc_df["risk_level"] == filter_level.upper()]
        if min_duration > 0:
            inc_df = inc_df[inc_df["duration_days"] >= min_duration]

        top = inc_df.head(n)
        result = []
        for _, row in top.iterrows():
            result.append({
                "priority_rank":   int(row["priority_rank"]),
                "event_id":        str(row["event_id"]),
                "event_type":      str(row["event_type"]),
                "city":            str(row.get("city", "")),
                "risk_score":      int(row["risk_score"]),
                "risk_level":      str(row["risk_level"]),
                "severity":        str(row.get("severity", "Low")),
                "detection_count": int(row["detection_count"]),
                "duration_days":   int(row["duration_days"]),
                "max_frp":         float(row["max_frp"]),
                "latest_detection":str(row["latest_detection"]),
            })
        return jsonify({"priority_queue": result, "total": len(result)})
    except Exception as e:
        log.exception("priority queue error")
        return jsonify({"error": str(e)}), 500


@incidents_bp.route("/api/replay")
@login_required
def api_replay():
    """Return daily aggregated detections for timeline replay."""
    try:
        year  = request.args.get("year", 2024, type=int)
        month = request.args.get("month", type=int)

        df = get_df()
        sub = df[df["year"] == year].copy()
        if month:
            sub = sub[sub["month"] == month]

        sub["date_str"] = sub["acq_date"].dt.strftime("%Y-%m-%d")
        groups = []
        for date_str, grp in sub.groupby("date_str"):
            groups.append({
                "date":         date_str,
                "total":        int(len(grp)),
                "fire":         int((grp["label"]==1).sum()),
                "flood":        int((grp["label"]==2).sum()),
                "avg_frp":      round(float(grp[grp["label"]==1]["frp"].mean()), 2)
                                if (grp["label"]==1).any() else 0,
                "high_sev":     int((grp["severity"]=="High").sum())
                                if "severity" in grp.columns else 0,
            })

        groups.sort(key=lambda x: x["date"])
        return jsonify({
            "year":        year,
            "month":       month,
            "daily_data":  groups,
            "total_days":  len(groups),
        })
    except Exception as e:
        log.exception("replay error")
        return jsonify({"error": str(e)}), 500
