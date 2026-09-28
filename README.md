# 🛡️ GEOSHIELD — AI-Powered Satellite Disaster Management System

> Real-time Wildfire & Flood Detection using NASA VIIRS JPSS-1 Satellite Data

![Python](https://img.shields.io/badge/Python-3.10+-blue) 
![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-orange)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green)

---

## 📋 Overview

GEOSHIELD is an end-to-end AI/ML system that:
- 🔍 **Detects** wildfires and floods from NASA VIIRS JPSS-1 satellite CSV data
- 🤖 **Classifies** events using a CNN deep learning model (Fire / Flood / Normal)
- 🗺️ **Visualises** results on an interactive GIS map with severity overlays
- 📊 **Analyses** year-wise (2022–2024) trends in disaster frequency and intensity
- 🚨 **Alerts** via email/SMS when high-confidence events are detected

---

## 🗂️ Project Structure

```
GEOSHIELD/
├── config.py                   ← Global configuration & thresholds
├── train.py                    ← Full training pipeline (CLI)
├── requirements.txt
├── data/
│   └── viirs-jpss1_*/          ← VIIRS CSV data folders
├── src/
│   ├── data_loader.py          ← Step 1: Data loading, cleaning, NDVI/NBR
│   ├── generate_data.py        ← Synthetic data generator (if no CSVs)
│   ├── model_cnn.py            ← Step 2: CNN Fire/Flood classifier
│   ├── model_unet.py           ← Step 2: UNet spatial segmentation
│   ├── risk_analysis.py        ← Step 3: Severity + trend analysis
│   ├── map_builder.py          ← Step 4: Interactive Folium GIS map
│   └── alert_system.py         ← Step 5: SQLite logging + Email/SMS
├── app/
│   ├── streamlit_app.py        ← Main Streamlit dashboard
│   └── api.py                  ← FastAPI REST backend
├── models/                     ← Saved model checkpoints
├── outputs/
│   ├── maps/                   ← Generated HTML maps
│   └── reports/                ← Trend chart PNGs
└── alerts/
    └── alerts.db               ← SQLite alert database
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Add Data (or use synthetic)
Place VIIRS CSV files in the appropriate year folders:
```
data/viirs-jpss1_2022_all_countries/viirs-jpss1/2022/
data/viirs-jpss1_2023_all_countries/viirs-jpss1/2023/
data/viirs-jpss1_2024_all_countries/viirs-jpss1/2024/
```
Or let the system auto-generate synthetic data on first run.

### 3. Train Models
```bash
python train.py                 # Full pipeline (CNN + UNet)
python train.py --cnn-only      # Only CNN classifier
python train.py --unet-only     # Only UNet segmentation
python train.py --epochs 20     # Custom epoch count
```

### 4. Launch Dashboard
```bash
streamlit run app/streamlit_app.py
```

### 5. Launch REST API (optional)
```bash
python app/api.py
# API docs: http://localhost:8000/docs
```

---

## 📊 Dataset

**NASA VIIRS JPSS-1 Active Fire Data**
- Source: [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/)
- Columns: `latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, confidence, version, bright_t31, frp, daynight`

---

## 🤖 AI Models

### CNN Classifier (`src/model_cnn.py`)
- **Architecture**: 4-block FC network with BatchNorm + Dropout
- **Features**: `brightness, scan, track, bright_t31, frp, ndvi, nbr` (7 features)
- **Classes**: Normal (0), Fire (1), Flood (2)
- **Target Accuracy**: 88–92%

### UNet Segmentation (`src/model_unet.py`)
- **Architecture**: Encoder-decoder with skip connections
- **Input**: 3-channel 64×64 spatial grid (FRP, brightness, confidence)
- **Output**: Per-pixel Fire/Flood/Normal mask → GeoJSON polygons

---

## 🗺️ Dashboard Features

| Tab | Features |
|-----|----------|
| 🏠 Overview | KPI metrics, detection trends, severity donut charts |
| 🗺️ Live Map | Folium map with clusters, heat map, layer control |
| 📊 Analytics | Year-wise charts, monthly heatmap, hotspot table |
| 🤖 AI Predict | Single-row prediction form + CSV batch upload |
| 🚨 Alerts | Alert log, live scanning, high-severity notifications |
| 🔎 Data Explorer | Raw data table, statistics, CSV download |

---

## 🚨 Alert Configuration

Set these environment variables to enable notifications:

```bash
# Email (Gmail)
SMTP_USER=your_gmail@gmail.com
SMTP_PASSWORD=your_app_password
ALERT_TO=recipient@email.com

# SMS (Twilio)
TWILIO_SID=your_account_sid
TWILIO_TOKEN=your_auth_token
TWILIO_FROM=+1234567890
TWILIO_TO=+0987654321
```

---

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/api/status` | System & model status |
| POST | `/api/predict` | Run AI prediction |
| GET | `/api/alerts` | Fetch alert log |
| GET | `/api/alerts/stats` | Alert statistics |
| GET | `/api/data/summary` | Dataset summary |

---

## 📈 Spectral Indices

| Index | Formula | Interpretation |
|-------|---------|----------------|
| NDVI proxy | `(T31 - T21) / (T31 + T21)` | Vegetation health (negative in fire zones) |
| NBR proxy | `(T21 - FRP) / (T21 + FRP)` | Burn ratio (high = active fire) |

---

## 📄 License

MIT License — Built for academic research and disaster response applications.
