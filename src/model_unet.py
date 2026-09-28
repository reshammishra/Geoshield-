"""
GEOSHIELD — UNet Segmentation Model (Step 2)
Converts lat/lon VIIRS detections into a 2D spatial grid,
then applies a UNet architecture to produce pixel-wise
Fire/Flood/Normal segmentation masks.

The output mask is converted to GeoJSON polygons representing
detected affected zone boundaries.
"""

import logging
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    GRID_SIZE, UNET_MODEL_PATH, MODELS_DIR,
    RANDOM_SEED, BATCH_SIZE, EPOCHS, LEARNING_RATE,
    TRAIN_TEST_SPLIT
)

log = logging.getLogger("GeoShield.UNet")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ─────────────────────────────────────────────────────────────────────────────
# UNet Building Blocks
# ─────────────────────────────────────────────────────────────────────────────

class _DoubleConv(nn.Module):
    """Two consecutive Conv2d → BN → ReLU layers."""

    def __init__(self, in_ch: int, out_ch: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class _Down(nn.Module):
    """Downsample with MaxPool → DoubleConv."""

    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.pool_conv = nn.Sequential(nn.MaxPool2d(2), _DoubleConv(in_ch, out_ch))

    def forward(self, x):
        return self.pool_conv(x)


class _Up(nn.Module):
    """Bilinear upsample → concat skip → DoubleConv."""

    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.up   = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
        self.conv = _DoubleConv(in_ch, out_ch)

    def forward(self, x, skip):
        x    = self.up(x)
        # Pad if spatial dims differ (odd-sized inputs)
        diff_h = skip.size(2) - x.size(2)
        diff_w = skip.size(3) - x.size(3)
        x = F.pad(x, [diff_w // 2, diff_w - diff_w // 2,
                       diff_h // 2, diff_h - diff_h // 2])
        return self.conv(torch.cat([skip, x], dim=1))


class GeoUNet(nn.Module):
    """
    Lightweight UNet for 64×64 spatial grid segmentation.
    Input:  (B, in_channels, H, W)  — 3-channel feature maps
    Output: (B, num_classes, H, W)  — per-pixel class logits
    """

    def __init__(self, in_channels: int = 3, num_classes: int = 3, base_ch: int = 32):
        super().__init__()
        c = base_ch
        self.inc   = _DoubleConv(in_channels, c)
        self.down1 = _Down(c,    c*2)
        self.down2 = _Down(c*2,  c*4)
        self.down3 = _Down(c*4,  c*8)
        self.bot   = _Down(c*8,  c*8)   # bottleneck

        self.up1   = _Up(c*8 + c*8, c*8)
        self.up2   = _Up(c*8 + c*4, c*4)
        self.up3   = _Up(c*4 + c*2, c*2)
        self.up4   = _Up(c*2 + c,   c)
        self.out   = nn.Conv2d(c, num_classes, kernel_size=1)

    def forward(self, x):
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)
        x5 = self.bot(x4)

        x  = self.up1(x5, x4)
        x  = self.up2(x,  x3)
        x  = self.up3(x,  x2)
        x  = self.up4(x,  x1)
        return self.out(x)


# ─────────────────────────────────────────────────────────────────────────────
# Grid Encoding
# ─────────────────────────────────────────────────────────────────────────────

def df_to_grid(df, lat_min=-90, lat_max=90, lon_min=-180, lon_max=180):
    """
    Convert VIIRS point detections into a (3, GRID_SIZE, GRID_SIZE) feature map.

    Channels:
      0 — normalised FRP (fire radiative power)
      1 — normalised brightness
      2 — normalised confidence
    """
    G  = GRID_SIZE
    grid = np.zeros((3, G, G), dtype=np.float32)
    cnt  = np.zeros((G, G),    dtype=np.float32)

    # Map lat/lon to grid indices
    row_idx = ((df["latitude"]  - lat_min) / (lat_max - lat_min) * (G - 1)).clip(0, G-1).astype(int)
    col_idx = ((df["longitude"] - lon_min) / (lon_max - lon_min) * (G - 1)).clip(0, G-1).astype(int)

    for i, (r, c) in enumerate(zip(row_idx, col_idx)):
        grid[0, r, c] += df["frp"].iloc[i]
        grid[1, r, c] += df["brightness"].iloc[i]
        grid[2, r, c] += df["confidence"].iloc[i]
        cnt[r, c]     += 1

    # Average where cells received multiple detections
    mask = cnt > 0
    for ch in range(3):
        grid[ch][mask] /= cnt[mask]

    # Normalise each channel to [0, 1]
    for ch in range(3):
        ch_max = grid[ch].max()
        if ch_max > 0:
            grid[ch] /= ch_max

    return grid   # (3, G, G)


def df_to_label_grid(df, lat_min=-90, lat_max=90, lon_min=-180, lon_max=180):
    """Convert VIIRS labels to a (GRID_SIZE, GRID_SIZE) integer label grid."""
    G    = GRID_SIZE
    lgrid = np.zeros((G, G), dtype=np.int64)
    conf  = np.zeros((G, G), dtype=np.float32)   # confidence weighting

    row_idx = ((df["latitude"]  - lat_min) / (lat_max - lat_min) * (G-1)).clip(0, G-1).astype(int)
    col_idx = ((df["longitude"] - lon_min) / (lon_max - lon_min) * (G-1)).clip(0, G-1).astype(int)

    for i, (r, c) in enumerate(zip(row_idx, col_idx)):
        c_val = df["confidence"].iloc[i]
        if c_val > conf[r, c]:          # higher confidence wins
            conf[r, c]  = c_val
            lgrid[r, c] = int(df["label"].iloc[i])

    return lgrid  # (G, G)


def generate_tile_dataset(df, tile_size: int = GRID_SIZE, n_tiles: int = 200):
    """
    Generate N random regional tiles (sub-grids) from the full dataset.
    Each tile covers a 10°×10° region around a random detection.
    """
    np.random.seed(RANDOM_SEED)
    X_tiles, y_tiles = [], []

    for _ in range(n_tiles):
        # Pick a random detection as center
        sample = df.sample(1).iloc[0]
        lat_c, lon_c = sample["latitude"], sample["longitude"]
        delta = 5.0

        lat_min, lat_max = lat_c - delta, lat_c + delta
        lon_min, lon_max = lon_c - delta, lon_c + delta

        subset = df[
            (df["latitude"].between(lat_min, lat_max)) &
            (df["longitude"].between(lon_min, lon_max))
        ]

        if len(subset) < 3:
            continue

        X = df_to_grid(subset, lat_min, lat_max, lon_min, lon_max)
        y = df_to_label_grid(subset, lat_min, lat_max, lon_min, lon_max)

        X_tiles.append(X)
        y_tiles.append(y)

    if not X_tiles:
        raise ValueError("Could not generate any tiles from the dataset.")

    return np.array(X_tiles, dtype=np.float32), np.array(y_tiles, dtype=np.int64)


# ─────────────────────────────────────────────────────────────────────────────
# Training
# ─────────────────────────────────────────────────────────────────────────────

def train_unet(df, save: bool = True):
    """
    Train UNet segmentation model on tile dataset derived from df.

    Returns
    -------
    model : GeoUNet
    metrics : dict
    """
    log.info("Generating tile dataset for UNet training …")
    X, y = generate_tile_dataset(df, n_tiles=300)
    log.info(f"Tiles: X={X.shape}, y={y.shape}")

    # Split
    split = int(len(X) * (1 - TRAIN_TEST_SPLIT))
    X_tr, X_te = X[:split], X[split:]
    y_tr, y_te = y[:split], y[split:]

    train_loader = DataLoader(
        TensorDataset(
            torch.tensor(X_tr),
            torch.tensor(y_tr),
        ),
        batch_size=4, shuffle=True
    )

    model     = GeoUNet(in_channels=3, num_classes=3).to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    best_loss = float("inf")

    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch = X_batch.to(DEVICE)
            y_batch = y_batch.to(DEVICE)
            optimizer.zero_grad()
            logits = model(X_batch)
            loss   = criterion(logits, y_batch)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        avg_loss = total_loss / len(train_loader)
        scheduler.step()

        if epoch % 5 == 0 or epoch == 1:
            log.info(f"UNet Epoch {epoch:3d}/{EPOCHS} | Loss: {avg_loss:.4f}")

        if avg_loss < best_loss and save:
            best_loss = avg_loss
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model_state": model.state_dict(),
                "in_channels": 3,
                "num_classes": 3,
                "grid_size"  : GRID_SIZE,
            }, UNET_MODEL_PATH)

    log.info(f"UNet training complete. Best loss: {best_loss:.4f}")
    return model, {"best_loss": best_loss}


# ─────────────────────────────────────────────────────────────────────────────
# Inference & GeoJSON
# ─────────────────────────────────────────────────────────────────────────────

def load_unet_model():
    """Load saved UNet from disk."""
    if not UNET_MODEL_PATH.exists():
        raise FileNotFoundError(f"UNet model not found at {UNET_MODEL_PATH}.")
    ckpt  = torch.load(UNET_MODEL_PATH, map_location=DEVICE, weights_only=False)
    model = GeoUNet(
        in_channels=ckpt["in_channels"],
        num_classes=ckpt["num_classes"]
    ).to(DEVICE)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model


def predict_mask(df_region, lat_min, lat_max, lon_min, lon_max):
    """
    Run UNet on a regional subset and return predicted class mask (GRID_SIZE×GRID_SIZE).
    """
    model = load_unet_model()
    X = df_to_grid(df_region, lat_min, lat_max, lon_min, lon_max)
    X_t = torch.tensor(X[np.newaxis], dtype=torch.float32).to(DEVICE)
    with torch.no_grad():
        logits = model(X_t)
        mask   = logits.argmax(dim=1).squeeze(0).cpu().numpy()
    return mask  # (G, G) int array


def mask_to_geojson(mask, lat_min, lat_max, lon_min, lon_max):
    """
    Convert a (G, G) integer mask into a GeoJSON FeatureCollection
    where each unique class zone is a polygon.
    """
    import json
    G     = mask.shape[0]
    lat_s = (lat_max - lat_min) / G
    lon_s = (lon_max - lon_min) / G

    label_names = {0: "Normal", 1: "Fire", 2: "Flood"}
    features = []

    for cls in [1, 2]:   # Only export Fire and Flood polygons
        for r in range(G):
            for c in range(G):
                if mask[r, c] == cls:
                    lat0 = lat_min + r * lat_s
                    lon0 = lon_min + c * lon_s
                    # Simple square cell polygon
                    coords = [[
                        [lon0,       lat0],
                        [lon0+lon_s, lat0],
                        [lon0+lon_s, lat0+lat_s],
                        [lon0,       lat0+lat_s],
                        [lon0,       lat0],
                    ]]
                    features.append({
                        "type": "Feature",
                        "properties": {
                            "class"     : cls,
                            "label"     : label_names[cls],
                            "row"       : r,
                            "col"       : c,
                        },
                        "geometry": {
                            "type"       : "Polygon",
                            "coordinates": coords,
                        }
                    })

    return {"type": "FeatureCollection", "features": features}


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pandas as pd
    from src.data_loader import load_all_data

    log.info("=== GEOSHIELD UNet Training ===")
    df = load_all_data(save=False)
    model, metrics = train_unet(df, save=True)
    print(f"\n✅ UNet training complete. Best loss: {metrics['best_loss']:.4f}")
    print(f"   Model saved → {UNET_MODEL_PATH}")
