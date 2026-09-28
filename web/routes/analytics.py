"""GeoShield – Analytics, Data Explorer, Data Quality routes"""
import io
import logging
import numpy as np
from flask import (Blueprint, render_template, jsonify, request,
                   session, Response)
from routes.auth import login_required
from services.data_service import (get_df, apply_filters, get_yearly_trends,
                                    get_city_summary, get_data_quality,
                                    get_summary_stats)

analytics_bp = Blueprint("analytics", __name__)
log = logging.getLogger("GeoShield.Analytics")


@analytics_bp.route("/analytics")
@login_required
def analytics_page():
    return render_template("analytics.html", user=session.get("user"))


@analytics_bp.route("/data-explorer")
@login_required
def data_explorer_page():
    return render_template("data_explorer.html", user=session.get("user"))


@analytics_bp.route("/data-health")
@login_required
def data_health_page():
    return render_template("data_health.html", user=session.get("user"))


# ── Analytics APIs ────────────────────────────────────────────────────────────

@analytics_bp.route("/api/analytics/trends")
@login_required
def api_trends():
    try:
        params = {
            "years":       request.args.getlist("years") or [],
            "event_types": request.args.getlist("event_types") or [],
        }
        df = get_df()
        filtered = apply_filters(df, params) if any(v for v in params.values()) else df
        return jsonify({"trends": get_yearly_trends(filtered)})
    except Exception as e:
        log.exception("trends error")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/api/analytics/cities")
@login_required
def api_cities():
    try:
        df = get_df()
        params = {
            "years":       request.args.getlist("years") or [],
            "event_types": request.args.getlist("event_types") or [],
        }
        filtered = apply_filters(df, params) if any(v for v in params.values()) else df
        return jsonify({"cities": get_city_summary(filtered)})
    except Exception as e:
        log.exception("cities error")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/api/analytics/monthly")
@login_required
def api_monthly():
    """Monthly detection breakdown for a given year."""
    try:
        year = request.args.get("year", 2024, type=int)
        df   = get_df()
        sub  = df[df["year"] == year]
        rows = []
        for month, grp in sub.groupby("month"):
            rows.append({
                "month":     int(month),
                "total":     int(len(grp)),
                "fire":      int((grp["label"]==1).sum()),
                "flood":     int((grp["label"]==2).sum()),
                "avg_frp":   round(float(grp[grp["label"]==1]["frp"].mean()), 2)
                             if (grp["label"]==1).any() else 0,
            })
        rows.sort(key=lambda x: x["month"])
        return jsonify({"year": year, "monthly": rows})
    except Exception as e:
        log.exception("monthly error")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/api/analytics/heatmap-data")
@login_required
def api_heatmap_data():
    """Return sampled lat/lon/weight for leaflet heatmap layer."""
    try:
        df      = get_df()
        label   = request.args.get("label", type=int)  # 1=fire, 2=flood
        year    = request.args.get("year", type=int)
        max_pts = request.args.get("max", 5000, type=int)

        sub = df.copy()
        if label is not None:
            sub = sub[sub["label"] == label]
        if year:
            sub = sub[sub["year"] == year]

        # Sample for performance
        if len(sub) > max_pts:
            sub = sub.sample(max_pts, random_state=42)

        # Normalise FRP for heatmap weight (0-1)
        frp_max = float(sub["frp"].max()) if len(sub) and sub["frp"].max() > 0 else 1
        points = []
        for _, row in sub.iterrows():
            weight = min(1.0, float(row["frp"]) / frp_max) if frp_max > 0 else 0.5
            points.append([float(row["latitude"]), float(row["longitude"]), weight])

        return jsonify({"points": points, "total": len(points)})
    except Exception as e:
        log.exception("heatmap error")
        return jsonify({"error": str(e)}), 500


# ── Data Explorer APIs ────────────────────────────────────────────────────────

@analytics_bp.route("/api/data/records")
@login_required
def api_records():
    """Paginated raw records endpoint."""
    try:
        page     = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 100, type=int), 500)
        params   = {
            "years":          request.args.getlist("years") or [],
            "event_types":    request.args.getlist("event_types") or [],
            "severity_levels":request.args.getlist("severity") or [],
            "confidence_min": request.args.get("confidence_min", 0, type=float),
            "date_from":      request.args.get("date_from"),
            "date_to":        request.args.get("date_to"),
            "city":           request.args.get("city"),
        }
        sort_col = request.args.get("sort", "frp")
        sort_asc = request.args.get("asc", "false").lower() == "true"

        df       = get_df()
        filtered = apply_filters(df, params)

        # Sort
        if sort_col in filtered.columns:
            filtered = filtered.sort_values(sort_col, ascending=sort_asc)

        total = len(filtered)
        start = (page - 1) * per_page
        chunk = filtered.iloc[start:start + per_page]

        display_cols = ["acq_date","city","latitude","longitude",
                        "brightness","frp","confidence","label","year","month"]
        if "severity" in chunk.columns:
            display_cols.append("severity")
        if "area_km2" in chunk.columns:
            display_cols.append("area_km2")
        chunk = chunk[[c for c in display_cols if c in chunk.columns]]

        records = []
        for _, row in chunk.iterrows():
            rec = {}
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    rec[k] = str(v)[:10]
                elif isinstance(v, (np.integer,)):
                    rec[k] = int(v)
                elif isinstance(v, (np.floating,)):
                    rec[k] = round(float(v), 4) if np.isfinite(v) else None
                else:
                    rec[k] = v
            rec["event_type"] = {0:"Normal",1:"Fire",2:"Flood"}.get(rec.get("label",0),"Unknown")
            records.append(rec)

        return jsonify({
            "page":     page,
            "per_page": per_page,
            "total":    total,
            "pages":    max(1, (total + per_page - 1) // per_page),
            "records":  records,
        })
    except Exception as e:
        log.exception("records error")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/api/data/export")
@login_required
def api_export():
    """Export filtered dataset as CSV (streamed)."""
    try:
        params = {
            "years":          request.args.getlist("years") or [],
            "event_types":    request.args.getlist("event_types") or [],
            "severity_levels":request.args.getlist("severity") or [],
            "confidence_min": request.args.get("confidence_min", 0, type=float),
            "date_from":      request.args.get("date_from"),
            "date_to":        request.args.get("date_to"),
            "city":           request.args.get("city"),
        }
        df       = get_df()
        filtered = apply_filters(df, params)

        # Convert acq_date to string
        filtered = filtered.copy()
        if "acq_date" in filtered.columns:
            filtered["acq_date"] = filtered["acq_date"].astype(str).str[:10]

        buf = io.StringIO()
        filtered.to_csv(buf, index=False)
        buf.seek(0)

        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=geoshield_export.csv"},
        )
    except Exception as e:
        log.exception("export error")
        return jsonify({"error": str(e)}), 500


@analytics_bp.route("/api/search")
@login_required
def api_search():
    """Global search across city, event_id, and event type."""
    try:
        q = request.args.get("q", "").strip()
        if not q or len(q) < 2:
            return jsonify({"results": [], "total": 0})

        from services.event_fusion import fuse_events
        df    = get_df()
        inc   = fuse_events(df, event_type="all")

        results = []
        q_lower = q.lower()

        # Search incidents
        for _, row in inc.iterrows():
            if (q_lower in str(row.get("city","")).lower() or
                q_lower in str(row.get("event_id","")).lower() or
                q_lower in str(row.get("event_type","")).lower()):
                results.append({
                    "type":      "incident",
                    "event_id":  str(row["event_id"]),
                    "title":     f"{row['event_type']} – {row.get('city','Unknown')}",
                    "subtitle":  f"Risk {row['risk_score']}/100 · {row['detection_count']} detections",
                    "lat":       float(row["latitude"]),
                    "lon":       float(row["longitude"]),
                })
                if len(results) >= 20:
                    break

        return jsonify({"results": results, "total": len(results)})
    except Exception as e:
        log.exception("search error")
        return jsonify({"error": str(e)}), 500


# ── Data Quality API ──────────────────────────────────────────────────────────

@analytics_bp.route("/api/data-quality")
@login_required
def api_data_quality():
    try:
        return jsonify(get_data_quality())
    except Exception as e:
        log.exception("data quality error")
        return jsonify({"error": str(e)}), 500
