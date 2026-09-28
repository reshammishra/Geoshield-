"""
GEOSHIELD — Synthetic Data Generator
Generates realistic VIIRS JPSS-1 satellite CSV data for 2022, 2023, 2024.
Run this if no real CSV files are present in the data folders.
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_DIR, YEARS

# ─── Reproducibility ──────────────────────────────────────────────────────────
np.random.seed(42)

# ─── Known wildfire / flood hotspot regions ───────────────────────────────────
HOTSPOTS = [
    # (lat_center, lon_center, label_bias) — label_bias: 'fire' or 'flood'
    (37.5,  -119.5, "fire"),   # California, USA
    (-33.5,  150.0, "fire"),   # New South Wales, Australia
    ( 60.0,  100.0, "fire"),   # Siberia, Russia
    ( 25.0,   90.0, "flood"),  # Bangladesh
    (  5.0,   30.0, "flood"),  # South Sudan
    (-10.0,  -55.0, "fire"),   # Brazil Amazon
    ( 15.0,   40.0, "fire"),   # Ethiopia
    ( 50.0,   30.0, "fire"),   # Ukraine
    ( 20.0,   80.0, "flood"),  # India
    ( 30.0,  110.0, "flood"),  # China Yangtze
]


def _make_rows(n: int, year: int, hotspot: tuple) -> pd.DataFrame:
    """Generate n rows of synthetic VIIRS-style data near a hotspot."""
    lat_c, lon_c, bias = hotspot

    # Scatter around hotspot center
    lats = lat_c + np.random.uniform(-3, 3, n)
    lons = lon_c + np.random.uniform(-3, 3, n)

    # Brightness / FRP distributions differ by event type
    if bias == "fire":
        brightness = np.random.uniform(310, 420, n)
        frp        = np.random.uniform(30, 500, n)
        bright_t31 = brightness - np.random.uniform(5, 30, n)
    else:  # flood
        brightness = np.random.uniform(290, 330, n)
        frp        = np.random.uniform(0, 10, n)
        bright_t31 = brightness + np.random.uniform(0, 10, n)

    # Random dates in the given year
    days   = np.random.randint(1, 366, n)
    dates  = pd.to_datetime(f"{year}-01-01") + pd.to_timedelta(days, unit="D")
    dates  = dates.strftime("%Y-%m-%d")
    times  = np.random.randint(0, 2359, n)

    confidence = np.random.choice(
        [np.random.randint(51, 100)  for _ in range(n)],  # mostly above 50
    )
    # Some low-confidence rows to test filtering
    mask_low = np.random.random(n) < 0.1
    confidence = np.where(mask_low, np.random.randint(10, 50, n), np.random.randint(51, 100, n))

    scan  = np.random.uniform(0.3, 1.5, n)
    track = np.random.uniform(0.3, 1.5, n)

    return pd.DataFrame({
        "latitude"   : np.round(lats, 4),
        "longitude"  : np.round(lons, 4),
        "brightness" : np.round(brightness, 2),
        "scan"       : np.round(scan, 2),
        "track"      : np.round(track, 2),
        "acq_date"   : dates,
        "acq_time"   : times,
        "satellite"  : "JPSS-1",
        "confidence" : confidence,
        "version"    : "2.0NRT",
        "bright_t31" : np.round(bright_t31, 2),
        "frp"        : np.round(frp, 2),
        "daynight"   : np.random.choice(["D", "N"], n),
    })


def generate_data(rows_per_hotspot: int = 500) -> None:
    """Generate CSV files for 2022, 2023, 2024."""
    for year in YEARS:
        frames = []
        for hotspot in HOTSPOTS:
            frames.append(_make_rows(rows_per_hotspot, year, hotspot))

        df = pd.concat(frames, ignore_index=True)
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)  # shuffle

        # Resolve output path — check both old top-level data dir and new GEOSHIELD/data dir
        created = False
        for base in [
            DATA_DIR,
            Path(__file__).parent.parent.parent / f"viirs-jpss1_{year}_all_countries",
        ]:
            folder = base / f"viirs-jpss1_{year}_all_countries" / "viirs-jpss1" / str(year)
            if not folder.exists():
                folder = base / "viirs-jpss1" / str(year)
            if not folder.exists():
                folder.mkdir(parents=True, exist_ok=True)
            csv_path = folder / f"viirs-jpss1_{year}_India.csv"
            df.to_csv(csv_path, index=False)
            print(f"[OK] Saved {len(df)} rows -> {csv_path}")
            created = True
            break

        if not created:
            raise RuntimeError(f"Unable to create synthetic dataset for {year}")


if __name__ == "__main__":
    print("=== GEOSHIELD Synthetic Data Generator ===")
    generate_data(rows_per_hotspot=600)
    print("Done.")
