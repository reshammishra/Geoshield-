"""
GEOSHIELD — CNN Classifier (Step 2)
Trains a deep neural network to classify satellite detections as:
  0 = Normal  |  1 = Fire  |  2 = Flood

Architecture: Fully-connected CNN-style network with:
  BatchNorm → Dense → ReLU → Dropout (×3 blocks) → Softmax

Framework: PyTorch
"""

import logging
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    CNN_FEATURES, CNN_MODEL_PATH, TRAIN_TEST_SPLIT,
    RANDOM_SEED, BATCH_SIZE, EPOCHS, LEARNING_RATE, MODELS_DIR
)

log = logging.getLogger("GeoShield.CNN")
logging.basicConfig(level=logging.INFO,
                    format="[%(asctime)s] %(levelname)s — %(message)s",
                    datefmt="%H:%M:%S")

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
log.info(f"Using device: {DEVICE}")


# ─────────────────────────────────────────────────────────────────────────────
# Model Definition
# ─────────────────────────────────────────────────────────────────────────────

class FireFloodCNN(nn.Module):
    """
    Fully-connected network for tabular VIIRS feature classification.
    Uses BatchNorm + Dropout for regularisation.
    """

    def __init__(self, input_dim: int = 7, num_classes: int = 3):
        super().__init__()
        self.net = nn.Sequential(
            # Block 1
            nn.Linear(input_dim, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.3),

            # Block 2
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.25),

            # Block 3
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.2),

            # Block 4
            nn.Linear(64, 32),
            nn.ReLU(),

            # Output
            nn.Linear(32, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ─────────────────────────────────────────────────────────────────────────────
# Training Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _prepare_tensors(df, scaler=None):
    """Extract features, scale them, and convert to PyTorch tensors."""
    import pandas as pd

    # Drop rows with NaN in feature columns
    df_clean = df[CNN_FEATURES + ["label"]].dropna()

    X = df_clean[CNN_FEATURES].values.astype(np.float32)
    y = df_clean["label"].values.astype(np.int64)

    if scaler is None:
        scaler = StandardScaler()
        X = scaler.fit_transform(X)
    else:
        X = scaler.transform(X)

    return (
        torch.tensor(X, dtype=torch.float32),
        torch.tensor(y, dtype=torch.long),
        scaler,
    )


def _compute_class_weights(y: torch.Tensor, num_classes: int) -> torch.Tensor:
    """Inverse-frequency class weights to handle imbalanced data."""
    counts = torch.bincount(y, minlength=num_classes).float()
    weights = 1.0 / (counts + 1e-6)
    weights = weights / weights.sum() * num_classes
    return weights.to(DEVICE)


def train_model(df, save: bool = True):
    """
    Full training pipeline.

    Parameters
    ----------
    df : pd.DataFrame — cleaned dataset with CNN_FEATURES + 'label' columns
    save : bool — whether to save the trained model

    Returns
    -------
    model : FireFloodCNN
    scaler : StandardScaler
    metrics : dict — accuracy and classification report
    """
    log.info("Preparing training data …")
    X_tensor, y_tensor, scaler = _prepare_tensors(df)

    # Train / test split
    idx = np.arange(len(X_tensor))
    tr_idx, te_idx = train_test_split(idx, test_size=TRAIN_TEST_SPLIT,
                                      random_state=RANDOM_SEED, stratify=y_tensor.numpy())

    X_tr, y_tr = X_tensor[tr_idx].to(DEVICE), y_tensor[tr_idx].to(DEVICE)
    X_te, y_te = X_tensor[te_idx].to(DEVICE), y_tensor[te_idx].to(DEVICE)

    train_loader = DataLoader(
        TensorDataset(X_tr, y_tr),
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=0,
    )

    # Model, loss, optimizer, scheduler
    model      = FireFloodCNN(input_dim=len(CNN_FEATURES)).to(DEVICE)
    weights    = _compute_class_weights(y_tr, num_classes=3)
    criterion  = nn.CrossEntropyLoss(weight=weights)
    optimizer  = optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)
    scheduler  = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=4,
                                                       factor=0.5)

    best_acc  = 0.0
    patience  = 8
    no_improve = 0

    log.info(f"Training CNN for {EPOCHS} epochs on {len(X_tr)} samples …")

    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0

        for X_batch, y_batch in train_loader:
            optimizer.zero_grad()
            logits = model(X_batch)
            loss   = criterion(logits, y_batch)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            total_loss += loss.item() * len(X_batch)

        avg_loss = total_loss / len(X_tr)

        # Validation
        model.eval()
        with torch.no_grad():
            val_logits = model(X_te)
            val_preds  = val_logits.argmax(dim=1).cpu().numpy()
            val_acc    = accuracy_score(y_te.cpu().numpy(), val_preds)

        scheduler.step(1 - val_acc)
        log.info(f"Epoch {epoch:3d}/{EPOCHS} | Loss: {avg_loss:.4f} | Val Acc: {val_acc*100:.2f}%")

        # Early stopping + best model checkpoint
        if val_acc > best_acc:
            best_acc   = val_acc
            no_improve = 0
            if save:
                MODELS_DIR.mkdir(parents=True, exist_ok=True)
                torch.save({
                    "model_state": model.state_dict(),
                    "scaler": scaler,
                    "input_dim": len(CNN_FEATURES),
                    "num_classes": 3,
                    "features": CNN_FEATURES,
                    "best_acc": best_acc,
                }, CNN_MODEL_PATH)
        else:
            no_improve += 1
            if no_improve >= patience:
                log.info(f"Early stopping at epoch {epoch} — best val acc: {best_acc*100:.2f}%")
                break

    # Final evaluation
    model.eval()
    with torch.no_grad():
        final_preds = model(X_te).argmax(dim=1).cpu().numpy()
        y_true      = y_te.cpu().numpy()

    report = classification_report(y_true, final_preds,
                                   target_names=["Normal", "Fire", "Flood"],
                                   zero_division=0)
    cm     = confusion_matrix(y_true, final_preds)

    log.info(f"\nFinal Accuracy: {best_acc*100:.2f}%\n")
    log.info(f"Classification Report:\n{report}")
    log.info(f"Confusion Matrix:\n{cm}")

    return model, scaler, {
        "accuracy": best_acc,
        "report": report,
        "confusion_matrix": cm.tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Inference
# ─────────────────────────────────────────────────────────────────────────────

def load_cnn_model():
    """Load saved CNN model and scaler from disk."""
    if not CNN_MODEL_PATH.exists():
        raise FileNotFoundError(f"CNN model not found at {CNN_MODEL_PATH}. Run train.py first.")

    checkpoint = torch.load(CNN_MODEL_PATH, map_location=DEVICE, weights_only=False)
    model = FireFloodCNN(
        input_dim=checkpoint["input_dim"],
        num_classes=checkpoint["num_classes"]
    ).to(DEVICE)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, checkpoint["scaler"]


def predict_single(row: dict) -> dict:
    """
    Predict class and confidence for a single data point.

    Parameters
    ----------
    row : dict — must contain keys matching CNN_FEATURES

    Returns
    -------
    dict with keys: label_id, label_name, confidence, probabilities
    """
    model, scaler = load_cnn_model()
    x = np.array([[row.get(f, 0.0) for f in CNN_FEATURES]], dtype=np.float32)
    x = scaler.transform(x)
    x_tensor = torch.tensor(x, dtype=torch.float32).to(DEVICE)

    with torch.no_grad():
        logits = model(x_tensor)
        probs  = torch.softmax(logits, dim=1).cpu().numpy()[0]
        label_id = int(probs.argmax())

    label_names = ["Normal", "Fire", "Flood"]
    return {
        "label_id"    : label_id,
        "label_name"  : label_names[label_id],
        "confidence"  : float(probs[label_id]) * 100,
        "probabilities": {name: float(p)*100 for name, p in zip(label_names, probs)},
    }


def batch_predict(df) -> np.ndarray:
    """Predict labels for an entire DataFrame."""
    model, scaler = load_cnn_model()
    X = df[CNN_FEATURES].fillna(0).values.astype(np.float32)
    X = scaler.transform(X)
    X_tensor = torch.tensor(X, dtype=torch.float32).to(DEVICE)

    model.eval()
    with torch.no_grad():
        logits = model(X_tensor)
        preds  = logits.argmax(dim=1).cpu().numpy()

    return preds


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pandas as pd
    from src.data_loader import load_all_data

    log.info("=== GEOSHIELD CNN Training ===")
    df = load_all_data(save=True)
    model, scaler, metrics = train_model(df, save=True)
    print(f"\n✅ Training complete! Best accuracy: {metrics['accuracy']*100:.2f}%")
    print(f"   Model saved → {CNN_MODEL_PATH}")
