"""
GEOSHIELD — Data Loader & Cleaner (Step 1)
Loads VIIRS JPSS-1 CSV files (India data) from 2022/2023/2024 folders,
cleans data, filters by confidence, computes spectral indices,
and tags records with nearest Indian city.

Real NASA FIRMS column mapping applied here:
  bright_ti4  →  brightness   (Channel I4, ~4 µm fire detection band)
  bright_ti5  →  bright_t31   (Channel I5, ~11 µm ambient temperature)
  confidence  →  numeric       ('h'→90, 'n'→75, 'l'→33)
"""

import glob
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── Project root on path ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BASE_DIR, DATA_DIR, YEARS,
    CONFIDENCE_THRESHOLD, VIIRS_COLUMNS, VIIRS_RAW_COLUMNS,
    CONFIDENCE_DECODE, INDIA_ONLY, INDIA_CITIES,
    FIRE_FRP_THRESHOLD, FLOOD_FRP_THRESHOLD, FLOOD_BRIGHT_MAX,
    CLEANED_DATA_PATH
)

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s — %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("GeoShield.DataLoader")


# ─────────────────────────────────────────────────────────────────────────────
# 1.  CSV Discovery
# ─────────────────────────────────────────────────────────────────────────────

def _find_csv_files() -> list[Path]:
    """
    Search DATA_DIR for VIIRS CSV files.
    If INDIA_ONLY=True, only returns India-specific CSV files (fast).
    Supports nested folder structures as produced by NASA FIRMS downloads.
    """
    found = set()

    if INDIA_ONLY:
        # Only load India CSV files — much faster, focused analysis
        for year in YEARS:
            patterns = [
                str(DATA_DIR / f"viirs-jpss1_{year}_all_countries" / "**" / f"*{year}_India.csv"),
                str(DATA_DIR / "**" / f"*{year}_India.csv"),
            ]
            for pat in patterns:
                for f in glob.glob(pat, recursive=True):
                    found.add(Path(f))
        log.info(f"India-only mode: found {len(found)} India CSV file(s).")
    else:
        # Load all countries (very large — 500+ files)
        patterns = []
        for year in YEARS:
            patterns += [
                str(DATA_DIR / f"viirs-jpss1_{year}_all_countries" / "**" / "*.csv"),
                str(DATA_DIR / "**" / str(year) / "*.csv"),
                str(DATA_DIR / "**" / "*.csv"),
            ]
            patterns += [
                str(BASE_DIR.parent / f"viirs-jpss1_{year}_all_countries" / "**" / "*.csv"),
            ]
        for pat in patterns:
            for f in glob.glob(pat, recursive=True):
                found.add(Path(f))
        log.info(f"All-countries mode: found {len(found)} CSV file(s).")

    return sorted(found)


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Single-File Loader (with real column mapping)
# ─────────────────────────────────────────────────────────────────────────────

def _load_single_csv(path: Path) -> pd.DataFrame | None:
    """
    Load one VIIRS CSV, apply column renaming and type coercions.
    Handles both old (brightness/bright_t31) and new (bright_ti4/bright_ti5) schemas.
    Returns None on failure.
    """
    try:
        if path.stat().st_size <= 0:
            log.warning(f"Empty file: {path}")
            return None

        file_frames = []
        chunksize = 200_000
        try:
            reader = pd.read_csv(
                path,
                low_memory=False,
                on_bad_lines="skip",
                engine="c",
                chunksize=chunksize,
            )
            for chunk in reader:
                file_frames.append(chunk)
        except TypeError:
            reader = pd.read_csv(
                path,
                low_memory=False,
                on_bad_lines="skip",
                engine="c",
            )
            file_frames = [reader]

        if not file_frames:
            return None

        df = pd.concat(file_frames, ignore_index=True)
    except Exception as exc:
        log.warning(f"Could not read {path}: {exc}")
        return None

    if df.empty:
        log.warning(f"Empty file: {path}")
        return None

    # Lowercase + strip column names
    df.columns = df.columns.str.strip().str.lower()

    # Ensure confidence exists before using it
    if "confidence" not in df.columns:
        df["confidence"] = np.nan

    # ── Column rename: real NASA FIRMS → internal names ──────────────────────
    rename_map = {}
    if "bright_ti4" in df.columns:
        rename_map["bright_ti4"] = "brightness"
    if "bright_ti5" in df.columns:
        rename_map["bright_ti5"] = "bright_t31"
    if rename_map:
        df = df.rename(columns=rename_map)
        log.debug(f"{path.name}: renamed columns {rename_map}")

    # ── Confidence: decode string → numeric ──────────────────────────────────
    if df["confidence"].dtype == object:
        df["confidence"] = (
            df["confidence"]
            .astype(str)
            .str.strip().str.lower()
            .map(CONFIDENCE_DECODE)
            .fillna(75)
            .astype(float)
        )

    # ── Ensure all required internal columns exist ────────────────────────────
    for col in VIIRS_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan

    df = df[VIIRS_COLUMNS].copy()

    # ── Numeric type coercions ────────────────────────────────────────────────
    numeric_cols = ["latitude", "longitude", "brightness", "scan", "track",
                    "confidence", "bright_t31", "frp"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Parse acquisition date
    df["acq_date"] = pd.to_datetime(df["acq_date"], errors="coerce")

    return df


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Data Cleaning
# ─────────────────────────────────────────────────────────────────────────────

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply quality filters:
      - Drop rows with missing lat/lon/brightness/frp
      - Filter confidence > CONFIDENCE_THRESHOLD (default 50 numeric)
      - Remove geographic impossibilities
    """
    initial = len(df)

    # Drop rows missing critical spatial / radiometric fields
    df = df.dropna(subset=["latitude", "longitude", "brightness", "frp"])

    # Geographic sanity check
    df = df[df["latitude"].between(-90, 90) & df["longitude"].between(-180, 180)]

    # Confidence filter (numeric now)
    df = df[df["confidence"] >= CONFIDENCE_THRESHOLD]

    # FRP sanity (no negative power)
    df = df[df["frp"] >= 0]

    log.info(f"Cleaning: {initial:,} → {len(df):,} rows "
             f"({initial - len(df):,} removed, {len(df)/max(initial,1)*100:.1f}% retained)")
    return df.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Feature Engineering
# ─────────────────────────────────────────────────────────────────────────────

def _add_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add derived spectral-index proxies, temporal features, and city tags.

    NDVI proxy  = (bright_t31 - brightness) / (bright_t31 + brightness + ε)
        Vegetation index: negative in fire zones (vegetation burned off).

    NBR proxy   = (brightness - frp) / (brightness + frp + ε)
        Burn ratio: high where fire radiative power is high.

    Note: True NDVI/NBR need multi-spectral imagery; these are
    luminosity-based approximations from thermal bands only.
    """
    eps = 1e-5

    df["ndvi"] = (df["bright_t31"] - df["brightness"]) / \
                 (df["bright_t31"] + df["brightness"] + eps)
    df["ndvi"] = df["ndvi"].clip(-1, 1)

    df["nbr"]  = (df["brightness"] - df["frp"]) / \
                 (df["brightness"] + df["frp"] + eps)
    df["nbr"]  = df["nbr"].clip(-1, 1)

    # Temporal decomposition
    df["year"]  = df["acq_date"].dt.year
    df["month"] = df["acq_date"].dt.month
    df["doy"]   = df["acq_date"].dt.dayofyear   # day-of-year

    return df


# ─────────────────────────────────────────────────────────────────────────────
# 5.  City Tagging  (nearest-city, vectorised — no "Other")
# ─────────────────────────────────────────────────────────────────────────────

def _tag_cities(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign every row to the *nearest* city in INDIA_CITIES using
    fast vectorised numpy distance computation.

    Strategy:
      1. Build arrays of city centre lat/lon from INDIA_CITIES.
      2. Broadcast lat/lon of all rows against all city centres.
      3. Compute squared Euclidean distance (degrees) — good enough
         for nearest-neighbour classification inside India.
      4. argmin selects the closest city for every row.

    Result: no row is ever labelled "Other"; each gets the nearest
    named city even if it is far from any urban centre.
    """
    # Build lookup arrays (skip the "All India" sentinel whose value is None)
    cities_filtered = {k: v for k, v in INDIA_CITIES.items() if v is not None}
    city_names = list(cities_filtered.keys())
    city_lats  = np.array([v[0] for v in cities_filtered.values()])
    city_lons  = np.array([v[1] for v in cities_filtered.values()])

    lats = df["latitude"].values   # shape (N,)
    lons = df["longitude"].values  # shape (N,)

    # Squared distance to every city — shape (N, C)
    lat_diff = lats[:, np.newaxis] - city_lats[np.newaxis, :]
    lon_diff = lons[:, np.newaxis] - city_lons[np.newaxis, :]
    dist_sq  = lat_diff ** 2 + lon_diff ** 2

    nearest_idx  = np.argmin(dist_sq, axis=1)           # shape (N,)
    df["city"]   = [city_names[i] for i in nearest_idx]

    city_counts = df["city"].value_counts()
    log.info(f"Nearest-city tagging complete. Top cities: {dict(city_counts.head(8))}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Labelling
# ─────────────────────────────────────────────────────────────────────────────

def _assign_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rule-based labels (used as ground truth for model training):
      0 = Normal
      1 = Fire   — high FRP, high brightness
      2 = Flood  — very low FRP, moderate brightness (thermal anomaly near water)
    """
    conditions = [
        (df["frp"] > FIRE_FRP_THRESHOLD),
        (df["frp"] < FLOOD_FRP_THRESHOLD) & (df["brightness"] < FLOOD_BRIGHT_MAX),
    ]
    choices = [1, 2]   # Fire=1, Flood=2
    df["label"] = np.select(conditions, choices, default=0)   # 0=Normal

    counts = df["label"].value_counts().to_dict()
    log.info(f"Labels — Normal:{counts.get(0,0):,}, "
             f"Fire:{counts.get(1,0):,}, Flood:{counts.get(2,0):,}")
    return df



# ─────────────────────────────────────────────────────────────────────────────
# 7.  Memory Optimisation
# ─────────────────────────────────────────────────────────────────────────────

def _optimize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Downcast numeric columns and convert low-cardinality strings to category.
    Reduces DataFrame memory footprint by ~50% (float64→float32, int64→int8/int16).
    """
    # Float columns: float64 → float32 (halves memory, keeps enough precision)
    float_cols = ["brightness", "bright_t31", "frp", "scan", "track",
                  "ndvi", "nbr", "confidence"]
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].astype("float32")

    # Integer columns: int64 → smallest int type
    if "label" in df.columns:
        df["label"] = df["label"].astype("int8")      # values: 0,1,2
    if "type" in df.columns:
        df["type"] = df["type"].astype("int8")
    if "version" in df.columns:
        df["version"] = df["version"].astype("int8")
    for col in ["year", "month", "doy", "acq_time"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("int16")

    # Low-cardinality string columns → category (huge memory saving)
    for col in ["satellite", "daynight", "city", "severity"]:
        if col in df.columns:
            df[col] = df[col].astype("category")

    mem_mb = df.memory_usage(deep=True).sum() / 1_048_576
    log.info(f"Memory optimised: DataFrame is now {mem_mb:.1f} MB")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 8.  Public API
# ─────────────────────────────────────────────────────────────────────────────

def load_all_data(save: bool = True) -> pd.DataFrame:
    """
    Main entry point.
    Discovers India CSV files, loads, cleans, engineers features,
    tags cities, and assigns labels.

    Parameters
    ----------
    save : bool
        If True, saves cleaned data to CLEANED_DATA_PATH.

    Returns
    -------
    pd.DataFrame — cleaned, feature-engineered, city-tagged dataset
    """
    # ── Cache-first: load pre-cleaned parquet or CSV if it exists (instant load) ──
    parquet_path = CLEANED_DATA_PATH.with_suffix(".parquet")
    if parquet_path.exists():
        try:
            log.info(f"Loading cached high-speed parquet from {parquet_path} …")
            df_cached = pd.read_parquet(parquet_path)
            log.info(f"Parquet cache hit: {len(df_cached):,} rows loaded in seconds.")
            return _optimize_dtypes(df_cached)
        except Exception as e:
            log.warning(f"Parquet cache load failed ({e}) — falling back …")

    if CLEANED_DATA_PATH.exists() and CLEANED_DATA_PATH.stat().st_size > 1_000_000:
        try:
            log.info(f"Loading cached data from {CLEANED_DATA_PATH} …")
            dtypes = {
                'latitude': 'float32', 'longitude': 'float32', 'brightness': 'float32',
                'scan': 'float32', 'track': 'float32', 'confidence': 'float32',
                'bright_t31': 'float32', 'frp': 'float32', 'ndvi': 'float32', 'nbr': 'float32',
                'year': 'int16', 'month': 'int8', 'doy': 'int16', 'label': 'int8',
                'city': 'category', 'satellite': 'category', 'daynight': 'category'
            }
            df_cached = pd.read_csv(CLEANED_DATA_PATH, dtype=dtypes, low_memory=True)
            required_cols = {"latitude", "longitude", "brightness", "frp",
                             "confidence", "label", "city"}
            if required_cols.issubset(set(df_cached.columns)):
                log.info(f"Cache hit: {len(df_cached):,} rows loaded in seconds.")
                return _optimize_dtypes(df_cached)
            else:
                missing = required_cols - set(df_cached.columns)
                log.warning(f"Cache missing columns {missing} — rebuilding …")
        except Exception as e:
            log.warning(f"Cache load failed ({e}) — rebuilding from raw CSVs …")

    # ── Full reprocess from raw CSVs ──────────────────────────────────────────
    csv_files = _find_csv_files()

    if not csv_files:
        log.warning("No CSV files found! Falling back to synthetic data generation.")
        from src.generate_data import generate_data
        generate_data()
        csv_files = _find_csv_files()

    if not csv_files:
        raise FileNotFoundError(
            f"No VIIRS CSV files found under {DATA_DIR}. "
            "Please add CSV files or run src/generate_data.py first."
        )

    # Load all files
    frames = []
    for path in csv_files:
        df = _load_single_csv(path)
        if df is not None:
            frames.append(df)
            log.info(f"Loaded {len(df):,} rows from {path.name}")

    if not frames:
        log.warning("All CSV files failed to load. Generating fallback synthetic dataset.")
        try:
            from src.generate_data import generate_data
            generate_data(rows_per_hotspot=250)
            csv_files = _find_csv_files()
            frames = []
            for path in csv_files:
                df = _load_single_csv(path)
                if df is not None:
                    frames.append(df)
        except Exception as exc:
            log.warning(f"Fallback synthetic generation failed: {exc}")
            raise ValueError("All CSV files failed to load.") from exc

    if not frames:
        raise ValueError("All CSV files failed to load.")

    combined = pd.concat(frames, ignore_index=True)
    log.info(f"Combined raw data: {len(combined):,} rows from {len(frames)} file(s)")

    # Remove exact duplicates
    before = len(combined)
    combined = combined.drop_duplicates()
    log.info(f"Dropped {before - len(combined):,} duplicate rows")

    # Clean → Feature engineer → City tag → Label → Optimise memory
    combined = _clean(combined)
    combined = _add_features(combined)
    combined = _tag_cities(combined)
    combined = _assign_labels(combined)
    combined = _optimize_dtypes(combined)

    if save:
        CLEANED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(CLEANED_DATA_PATH, index=False)
        log.info(f"Saved cleaned data → {CLEANED_DATA_PATH}")

    return combined


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("=== GEOSHIELD Data Loader ===")
    df = load_all_data()
    print(f"\nDataset shape : {df.shape}")
    print(f"Columns       : {list(df.columns)}")
    print(f"Years covered : {sorted(df['year'].dropna().unique().tolist())}")
    print(f"Cities tagged : {df['city'].nunique()} unique cities")
    print(f"\nCity breakdown (top 10):")
    print(df['city'].value_counts().head(10).to_string())
    print(f"\nFirst 3 rows:")
    print(df.head(3).to_string())
