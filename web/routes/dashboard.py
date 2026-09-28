"""GeoShield – Dashboard routes"""
import logging
from flask import Blueprint, render_template, jsonify, request, session
from routes.auth import login_required
from services.data_service import (get_df, get_summary_stats,
                                    get_what_changed, apply_filters)

dashboard_bp = Blueprint("dashboard", __name__)
log = logging.getLogger("GeoShield.Dashboard")


@dashboard_bp.route("/dashboard")
@login_required
def dashboard_page():
    return render_template("dashboard.html", user=session.get("user"))


@dashboard_bp.route("/api/dashboard/summary")
@login_required
def api_summary():
    try:
        df = get_df()
        params = {
            "years": request.args.getlist("years") or [],
            "event_types": request.args.getlist("event_types") or [],
            "confidence_min": request.args.get("confidence_min", 50, type=float),
        }
        if any(v for v in params.values()):
            filtered = apply_filters(df, params)
        else:
            filtered = df
        return jsonify(get_summary_stats(filtered))
    except Exception as e:
        log.exception("summary error")
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/dashboard/what-changed")
@login_required
def api_what_changed():
    try:
        return jsonify(get_what_changed())
    except Exception as e:
        log.exception("what-changed error")
        return jsonify({"error": str(e)}), 500
