"""
GEOSHIELD — Global Configuration
All thresholds, paths, and constants used across modules.
"""

import os
from pathlib import Path

# ─── Base Paths ───────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DATA_DIR   = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
OUTPUTS_DIR= BASE_DIR / "outputs"
ALERTS_DIR = BASE_DIR / "alerts"
MAPS_DIR   = OUTPUTS_DIR / "maps"
REPORTS_DIR= OUTPUTS_DIR / "reports"

# Ensure output directories exist
for d in [MODELS_DIR, OUTPUTS_DIR, ALERTS_DIR, MAPS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Data Settings ────────────────────────────────────────────────────────────
YEARS                = [2022, 2023, 2024]
CONFIDENCE_THRESHOLD = 50      # Filter rows below this confidence (numeric after decode)
CLEANED_DATA_PATH    = OUTPUTS_DIR / "cleaned_data.csv"

# Load only India data (set False to load all countries — very slow)
INDIA_ONLY = True

# ── VIIRS JPSS-1 real column names (as they appear in NASA FIRMS downloads) ──
# bright_ti4 = Channel I4 brightness temp (fire detection band, ~4 µm)
# bright_ti5 = Channel I5 brightness temp (ambient/background, ~11 µm)
# confidence = 'h' (high ≥75%), 'n' (nominal ~50–75%), 'l' (low <50%)
VIIRS_RAW_COLUMNS = [
    "latitude", "longitude", "bright_ti4", "scan", "track",
    "acq_date", "acq_time", "satellite", "confidence",
    "version", "bright_ti5", "frp", "daynight", "type"
]

# Internal column names after renaming
VIIRS_COLUMNS = [
    "latitude", "longitude", "brightness", "scan", "track",
    "acq_date", "acq_time", "satellite", "confidence",
    "version", "bright_t31", "frp", "daynight", "type"
]

# Confidence string → numeric mapping (NASA FIRMS VIIRS)
CONFIDENCE_DECODE = {"h": 90, "n": 75, "l": 33}

# ─── India Major Cities ───────────────────────────────────────────────────────
# Format: city_name → (center_lat, center_lon, radius_deg)
# radius_deg ≈ km/111 ; 0.5° ≈ 55 km around city center
INDIA_CITIES = {
    "All India":        None,
    "Indore":           (22.7196, 75.8577, 0.6),
    "Delhi / NCR":      (28.6139, 77.2090, 0.8),
    "Mumbai":           (19.0760, 72.8777, 0.6),
    "Bengaluru":        (12.9716, 77.5946, 0.6),
    "Chennai":          (13.0827, 80.2707, 0.6),
    "Kolkata":          (22.5726, 88.3639, 0.6),
    "Hyderabad":        (17.3850, 78.4867, 0.6),
    "Pune":             (18.5204, 73.8567, 0.6),
    "Jaipur":           (26.9124, 75.7873, 0.6),
    "Lucknow":          (26.8467, 80.9462, 0.6),
    "Bhopal":           (23.2599, 77.4126, 0.6),
    "Ahmedabad":        (23.0225, 72.5714, 0.6),
    "Nagpur":           (21.1458, 79.0882, 0.6),
    "Surat":            (21.1702, 72.8311, 0.5),
    "Kanpur":           (26.4499, 80.3319, 0.5),
    "Patna":            (25.5941, 85.1376, 0.5),
    "Raipur":           (21.2514, 81.6296, 0.5),
    "Bhubaneswar":      (20.2961, 85.8245, 0.5),
    "Coimbatore":       (11.0168, 76.9558, 0.5),
    "Guwahati":         (26.1445, 91.7362, 0.5),
    "Dehradun":         (30.3165, 78.0322, 0.5),
    "Amritsar":         (31.6340, 74.8723, 0.5),
    "Visakhapatnam":    (17.6868, 83.2185, 0.5),
    "Varanasi":         (25.3176, 82.9739, 0.5),
    "Jodhpur":          (26.2389, 73.0243, 0.5),
    "Udaipur":          (24.5854, 73.7125, 0.5),
    "Gwalior":          (26.2183, 78.1828, 0.5),
    "Ranchi":           (23.3441, 85.3096, 0.5),
    "Thiruvananthapuram": (8.5241, 76.9366, 0.5),
    "Kochi":            (9.9312, 76.2673, 0.5),
    "Shimla":           (31.1048, 77.1734, 0.5),
}

# ─── Labeling Thresholds ──────────────────────────────────────────────────────
FIRE_FRP_THRESHOLD   = 50      # frp > 50 → Fire
FLOOD_FRP_THRESHOLD  = 5       # frp < 5  AND brightness < 320 → Flood proxy
FLOOD_BRIGHT_MAX     = 320

# Class labels
LABEL_MAP    = {0: "Normal", 1: "Fire", 2: "Flood"}
CLASS_WEIGHTS= {0: 1.0, 1: 2.0, 2: 2.5}   # Upweight minority classes

# ─── Severity Thresholds ──────────────────────────────────────────────────────
SEVERITY_HIGH_FRP   = 100
SEVERITY_HIGH_CONF  = 80
SEVERITY_MED_FRP_LO = 30
SEVERITY_MED_FRP_HI = 100
SEVERITY_MED_CONF_LO= 60
SEVERITY_MED_CONF_HI= 80

# Severity labels and colors for map markers
SEVERITY_COLORS = {
    "High"  : "#FF2D2D",   # Red
    "Medium": "#FFA500",   # Orange
    "Low"   : "#2ECC71",   # Green
}

# ─── Model Settings ───────────────────────────────────────────────────────────
CNN_FEATURES    = ["brightness", "scan", "track", "bright_t31", "frp", "ndvi", "nbr"]
CNN_MODEL_PATH  = MODELS_DIR / "cnn_classifier.pt"
UNET_MODEL_PATH = MODELS_DIR / "unet_segmentation.pt"

TRAIN_TEST_SPLIT = 0.2
RANDOM_SEED      = 42
BATCH_SIZE       = 64
EPOCHS           = 30
LEARNING_RATE    = 1e-3
GRID_SIZE        = 64   # UNet spatial grid (64×64 km tiles)

# ─── Alert Settings ───────────────────────────────────────────────────────────
ALERT_CONFIDENCE_THRESHOLD = 80   # Trigger alert if confidence > this

SMTP_HOST     = os.getenv("SMTP_HOST",  "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", 587))
SMTP_USER     = os.getenv("SMTP_USER",  "your_email@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your_app_password")
ALERT_TO      = os.getenv("ALERT_TO",   "alert_recipient@gmail.com")

TWILIO_SID    = os.getenv("TWILIO_SID",   "")
TWILIO_TOKEN  = os.getenv("TWILIO_TOKEN", "")
TWILIO_FROM   = os.getenv("TWILIO_FROM",  "")
TWILIO_TO     = os.getenv("TWILIO_TO",    "")

ALERTS_DB_PATH = ALERTS_DIR / "alerts.db"

# ─── Map Settings ─────────────────────────────────────────────────────────────
MAP_CENTER  = [22.5, 80.0]   # India center
MAP_ZOOM    = 5
MAP_OUTPUT  = MAPS_DIR / "geoshield_map.html"

# ─── FastAPI Settings ─────────────────────────────────────────────────────────
API_HOST = "0.0.0.0"
API_PORT = 8000
