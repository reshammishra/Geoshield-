"""GeoShield – Auth blueprint (login / signup / logout + SQLite users)"""

import hashlib
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, jsonify, flash)

ROOT = Path(__file__).parent.parent.parent
DB_PATH = ROOT / "alerts" / "geoshield_users.db"

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
log = logging.getLogger("GeoShield.Auth")


# ── DB init ───────────────────────────────────────────────────────────────────
def _init_user_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT    UNIQUE NOT NULL,
            email     TEXT    UNIQUE NOT NULL,
            password  TEXT    NOT NULL,
            role      TEXT    DEFAULT 'analyst',
            created_at TEXT   DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        )
    """)
    # Create default admin if none exists
    cur = conn.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        conn.execute("""
            INSERT INTO users (username, email, password, role)
            VALUES (?, ?, ?, ?)
        """, ("admin", "admin@geoshield.in", _hash("admin123"), "admin"))
        conn.execute("""
            INSERT INTO users (username, email, password, role)
            VALUES (?, ?, ?, ?)
        """, ("analyst", "analyst@geoshield.in", _hash("analyst123"), "analyst"))
        log.info("Default users created: admin/admin123, analyst/analyst123")
    conn.commit()
    conn.close()


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _get_user(username: str) -> dict | None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT * FROM users WHERE username=? OR email=?",
                       (username, username))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# ── Auth decorator ────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated


def role_required(role: str):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("auth.login"))
            if session["user"].get("role") not in (role, "admin"):
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Insufficient permissions"}), 403
                return render_template("error.html", code=403,
                                       message="You don't have permission to access this page."), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Routes ────────────────────────────────────────────────────────────────────
@auth_bp.before_app_request
def ensure_db():
    _init_user_db()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard.dashboard_page"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = _get_user(username)

        if user and user["password"] == _hash(password):
            session["user"] = {
                "id":       user["id"],
                "username": user["username"],
                "email":    user["email"],
                "role":     user["role"],
            }
            # Update last login
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("UPDATE users SET last_login=? WHERE id=?",
                         (datetime.utcnow().isoformat(), user["id"]))
            conn.commit()
            conn.close()
            next_url = request.args.get("next") or url_for("dashboard.dashboard_page")
            return redirect(next_url)
        else:
            error = "Invalid username or password."

    return render_template("login.html", error=error)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if "user" in session:
        return redirect(url_for("dashboard.dashboard_page"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")
        role     = request.form.get("role", "analyst")

        if not username or not email or not password:
            error = "All fields are required."
        elif password != confirm:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            try:
                conn = sqlite3.connect(str(DB_PATH))
                conn.execute(
                    "INSERT INTO users (username, email, password, role) VALUES (?,?,?,?)",
                    (username, email, _hash(password), role)
                )
                conn.commit()
                conn.close()
                return redirect(url_for("auth.login"))
            except sqlite3.IntegrityError:
                error = "Username or email already exists."

    return render_template("signup.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/me")
@login_required
def me():
    return jsonify(session.get("user", {}))
