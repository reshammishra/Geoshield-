"""
GeoShield – Flask Application Entry Point
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

from flask import Flask, jsonify, render_template, redirect, url_for, session, request

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("GeoShield.App")

# ── Create Flask app ──────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)
app.secret_key = "geoshield-secret-key-change-in-production-2024"

# ── Register blueprints ───────────────────────────────────────────────────────
from routes.auth      import auth_bp
from routes.dashboard import dashboard_bp
from routes.incidents import incidents_bp
from routes.analytics import analytics_bp
from routes.alerts    import alerts_bp
from routes.data      import data_bp
from routes.assistant import assistant_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(incidents_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(alerts_bp)
app.register_blueprint(data_bp)
app.register_blueprint(assistant_bp)


# ── Root redirect ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("auth.login"))
    return redirect(url_for("dashboard.dashboard_page"))


# ── Health check ──────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


# ── 404 / 500 handlers ────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Endpoint not found", "path": request.path}), 404
    return render_template("error.html", code=404, message="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    log.exception("Internal server error")
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error"}), 500
    return render_template("error.html", code=500, message="Internal server error"), 500


if __name__ == "__main__":
    log.info("=" * 60)
    log.info("  GeoShield — Satellite-to-Action Disaster Intelligence")
    log.info("  http://localhost:5000")
    log.info("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
