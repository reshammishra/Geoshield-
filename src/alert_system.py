"""
GEOSHIELD — Real-Time Alert System (Step 5)
Detects high-confidence events, logs to SQLite,
and optionally sends email/SMS notifications.
"""

import logging
import smtplib
import sqlite3
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    ALERT_CONFIDENCE_THRESHOLD,
    ALERTS_DB_PATH, ALERTS_DIR,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_TO,
    TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, TWILIO_TO
)

log = logging.getLogger("GeoShield.AlertSystem")
logging.basicConfig(level=logging.INFO,
                    format="[%(asctime)s] %(levelname)s — %(message)s",
                    datefmt="%H:%M:%S")

LABEL_NAMES = {0: "Normal", 1: "Fire", 2: "Flood"}


# ─────────────────────────────────────────────────────────────────────────────
# SQLite Database Setup
# ─────────────────────────────────────────────────────────────────────────────

def init_db() -> sqlite3.Connection:
    """
    Initialise the alerts SQLite database and create the alerts table
    if it does not already exist.
    """
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ALERTS_DB_PATH))
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
            sms_sent    INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def log_alert(conn: sqlite3.Connection, row: pd.Series,
              email_sent: bool = False, sms_sent: bool = False) -> int:
    """
    Insert one alert record into the SQLite database.

    Returns
    -------
    int — row ID of inserted alert
    """
    cursor = conn.execute("""
        INSERT INTO alerts
          (timestamp, acq_date, latitude, longitude, label, severity,
           frp, confidence, brightness, area_km2, satellite, email_sent, sms_sent)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        datetime.utcnow().isoformat(),
        str(row.get("acq_date", ""))[:10],
        float(row.get("latitude",  0)),
        float(row.get("longitude", 0)),
        LABEL_NAMES.get(int(row.get("label", 0)), "Unknown"),
        str(row.get("severity", "Low")),
        float(row.get("frp",        0)),
        float(row.get("confidence", 0)),
        float(row.get("brightness", 0)),
        float(row.get("area_km2",   0)),
        str(row.get("satellite", "JPSS-1")),
        int(email_sent),
        int(sms_sent),
    ))
    conn.commit()
    return cursor.lastrowid


def get_all_alerts(limit: int = 500) -> pd.DataFrame:
    """Fetch alert records from the database as a DataFrame."""
    conn = init_db()
    df   = pd.read_sql(
        f"SELECT * FROM alerts ORDER BY timestamp DESC LIMIT {limit}",
        conn
    )
    conn.close()
    return df


def get_alert_stats() -> dict:
    """Return summary statistics from the alerts database."""
    conn = init_db()
    cur  = conn.cursor()

    stats = {}
    cur.execute("SELECT COUNT(*) FROM alerts")
    stats["total"]  = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM alerts WHERE severity='High'")
    stats["high"]   = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM alerts WHERE label='Fire'")
    stats["fire"]   = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM alerts WHERE label='Flood'")
    stats["flood"]  = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM alerts WHERE email_sent=1")
    stats["emails"] = cur.fetchone()[0]

    conn.close()
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Email Alert
# ─────────────────────────────────────────────────────────────────────────────

def send_email_alert(row: pd.Series) -> bool:
    """
    Send an HTML email alert for a high-confidence detection.
    Returns True on success, False on failure (graceful).
    """
    if not SMTP_USER or SMTP_USER == "your_email@gmail.com":
        log.info("Email credentials not configured — skipping email alert.")
        return False

    label    = LABEL_NAMES.get(int(row.get("label", 0)), "Unknown")
    severity = str(row.get("severity", "Low"))
    lat      = float(row.get("latitude", 0))
    lon      = float(row.get("longitude", 0))
    frp      = float(row.get("frp", 0))
    conf     = float(row.get("confidence", 0))
    date_str = str(row.get("acq_date", ""))[:10]

    sev_color = {"High": "#FF2D2D", "Medium": "#FFA500", "Low": "#2ECC71"}.get(severity, "#aaa")
    subject   = f"🚨 GEOSHIELD ALERT: {severity} {label} Detected | FRP={frp:.0f} MW"

    html_body = f"""
    <html><body style="font-family:Arial; background:#0f0f1a; color:white; padding:20px;">
    <div style="max-width:600px; margin:auto; border-radius:12px; overflow:hidden;">
      <div style="background:linear-gradient(135deg,#1a1a2e,#16213e); padding:20px;
                  border-bottom:3px solid {sev_color}; text-align:center;">
        <h1 style="margin:0; color:{sev_color};">🛡️ GEOSHIELD ALERT</h1>
        <p style="margin:5px 0; font-size:18px;">
          {'🔥' if label=='Fire' else '🌊'} <b>{severity} {label} Detected</b>
        </p>
      </div>
      <div style="background:#16213e; padding:20px;">
        <table style="width:100%; border-collapse:collapse;">
          <tr style="border-bottom:1px solid #333;">
            <td style="padding:10px; color:#aaa;">📅 Detection Date</td>
            <td style="padding:10px; font-weight:bold;">{date_str}</td>
          </tr>
          <tr style="border-bottom:1px solid #333;">
            <td style="padding:10px; color:#aaa;">📍 Location</td>
            <td style="padding:10px;">{lat:.4f}°, {lon:.4f}°</td>
          </tr>
          <tr style="border-bottom:1px solid #333;">
            <td style="padding:10px; color:#aaa;">⚡ Fire Radiative Power</td>
            <td style="padding:10px; color:#FFA502; font-weight:bold;">{frp:.1f} MW</td>
          </tr>
          <tr style="border-bottom:1px solid #333;">
            <td style="padding:10px; color:#aaa;">🎯 Confidence</td>
            <td style="padding:10px;">{conf:.0f}%</td>
          </tr>
          <tr>
            <td style="padding:10px; color:#aaa;">🚨 Severity Level</td>
            <td style="padding:10px;"><span style="background:{sev_color}; color:#000;
                padding:3px 10px; border-radius:10px; font-weight:bold;">{severity}</span></td>
          </tr>
        </table>
        <div style="margin-top:16px; padding:12px; background:#1a1a2e; border-radius:8px;
                    border-left:4px solid {sev_color}; font-size:13px; color:#aaa;">
          ⚠️ This is an automated alert from GEOSHIELD — AI Satellite Disaster Management System.
          Immediate verification and response is recommended for High severity events.
        </div>
      </div>
    </div>
    </body></html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_USER
        msg["To"]      = ALERT_TO
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, ALERT_TO, msg.as_string())

        log.info(f"Email alert sent to {ALERT_TO}")
        return True

    except Exception as exc:
        log.warning(f"Email alert failed: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# SMS Alert (Twilio)
# ─────────────────────────────────────────────────────────────────────────────

def send_sms_alert(row: pd.Series) -> bool:
    """
    Send SMS alert via Twilio. Returns True on success.
    Gracefully skips if Twilio credentials are not configured.
    """
    if not TWILIO_SID or not TWILIO_TOKEN:
        log.info("Twilio credentials not configured — skipping SMS alert.")
        return False

    try:
        from twilio.rest import Client
        label    = LABEL_NAMES.get(int(row.get("label", 0)), "Unknown")
        severity = str(row.get("severity", "Low"))
        lat      = float(row.get("latitude", 0))
        lon      = float(row.get("longitude", 0))
        frp      = float(row.get("frp", 0))

        body = (
            f"🚨 GEOSHIELD ALERT\n"
            f"{severity} {label} detected!\n"
            f"Location: {lat:.3f}, {lon:.3f}\n"
            f"FRP: {frp:.0f} MW | Conf: {row.get('confidence',0):.0f}%\n"
            f"Date: {str(row.get('acq_date',''))[:10]}"
        )

        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(body=body, from_=TWILIO_FROM, to=TWILIO_TO)
        log.info(f"SMS alert sent to {TWILIO_TO}")
        return True

    except Exception as exc:
        log.warning(f"SMS alert failed: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Main Alert Processing
# ─────────────────────────────────────────────────────────────────────────────

def process_alerts(df: pd.DataFrame, send_notifications: bool = True) -> tuple[pd.DataFrame, int]:
    """
    Scan DataFrame for high-confidence events and trigger alerts.

    Parameters
    ----------
    df                   : Cleaned + risk-analyzed DataFrame
    send_notifications   : Whether to send email/SMS (set False for testing)

    Returns
    -------
    (alert_df, alert_count) — rows that triggered alerts, total count
    """
    conn = init_db()

    # Filter alert-worthy rows
    alert_mask = df["confidence"] > ALERT_CONFIDENCE_THRESHOLD
    alert_df   = df[alert_mask].copy()

    log.info(f"Processing {len(alert_df)} alert-worthy detections "
             f"(confidence > {ALERT_CONFIDENCE_THRESHOLD})")

    alert_count = 0
    for _, row in alert_df.iterrows():
        email_ok = send_email_alert(row) if send_notifications else False
        sms_ok   = send_sms_alert(row)   if send_notifications else False
        log_alert(conn, row, email_sent=email_ok, sms_sent=sms_ok)
        alert_count += 1

    conn.close()
    log.info(f"Logged {alert_count} alerts to {ALERTS_DB_PATH}")
    return alert_df, alert_count


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from src.data_loader import load_all_data
    from src.risk_analysis import run_risk_analysis

    log.info("=== GEOSHIELD Alert System ===")
    df = load_all_data(save=False)
    df_risk, _, _ = run_risk_analysis(df)
    alert_df, count = process_alerts(df_risk, send_notifications=False)

    print(f"\n✅ Alerts processed: {count}")
    stats = get_alert_stats()
    print(f"   Database stats: {stats}")
