"""
GEOSHIELD -- Full Training Pipeline
Run this script to train both CNN + UNet models end-to-end.
Usage: python train.py [--cnn-only] [--unet-only] [--epochs N]
"""

import argparse
import io
import logging
import sys
import time
from pathlib import Path

# Force UTF-8 stdout on Windows to handle special chars in log messages
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("GeoShield.Train")


def parse_args():
    parser = argparse.ArgumentParser(description="GEOSHIELD Model Training")
    parser.add_argument("--cnn-only",  action="store_true", help="Train only CNN classifier")
    parser.add_argument("--unet-only", action="store_true", help="Train only UNet segmentation")
    parser.add_argument("--epochs",    type=int, default=None,
                        help="Override number of training epochs")
    parser.add_argument("--no-save",   action="store_true", help="Don't save models to disk")
    return parser.parse_args()


def main():
    args = parse_args()

    # Optional epoch override
    if args.epochs is not None:
        import config as cfg
        cfg.EPOCHS = args.epochs
        log.info(f"Epoch override: {cfg.EPOCHS}")

    print("\n" + "="*60)
    print("   GEOSHIELD -- AI Model Training Pipeline")
    print("="*60 + "\n")

    # -- Step 1: Load Data ----------------------------------------------------
    log.info("STEP 1: Loading & cleaning satellite data ...")
    t0 = time.time()
    from src.data_loader import load_all_data
    df = load_all_data(save=True)
    log.info(f"Data loaded: {len(df):,} rows in {time.time()-t0:.1f}s\n")

    # -- Step 2: Risk Analysis (pre-compute before training) ------------------
    log.info("STEP 2: Running risk analysis ...")
    from src.risk_analysis import run_risk_analysis
    df_risk, trends, charts = run_risk_analysis(df)
    log.info(f"Risk analysis complete. Charts: {len(charts)}\n")

    # -- Step 3: Train CNN ----------------------------------------------------
    if not args.unet_only:
        log.info("STEP 3a: Training CNN Classifier ...")
        t1 = time.time()
        from src.model_cnn import train_model
        model_cnn, scaler, metrics = train_model(df_risk, save=not args.no_save)
        duration = time.time() - t1
        log.info(f"CNN Training complete | Accuracy: {metrics['accuracy']*100:.2f}% | "
                 f"Time: {duration:.1f}s\n")
        print("\n-- CNN Classification Report --")
        print(metrics["report"])

    # -- Step 4: Train UNet ---------------------------------------------------
    if not args.cnn_only:
        log.info("STEP 3b: Training UNet Segmentation ...")
        t2 = time.time()
        from src.model_unet import train_unet
        model_unet, unet_metrics = train_unet(df_risk, save=not args.no_save)
        duration = time.time() - t2
        log.info(f"UNet Training complete | Best loss: {unet_metrics['best_loss']:.4f} | "
                 f"Time: {duration:.1f}s\n")

    # -- Step 5: Alert Processing ---------------------------------------------
    log.info("STEP 4: Processing alerts ...")
    from src.alert_system import process_alerts, get_alert_stats
    _, alert_count = process_alerts(df_risk, send_notifications=False)
    stats = get_alert_stats()
    log.info(f"Alerts: {alert_count} logged | DB total: {stats}\n")

    # -- Step 6: Build Map ----------------------------------------------------
    log.info("STEP 5: Building interactive GIS map ...")
    from src.map_builder import save_map
    map_path = save_map(df_risk)
    log.info(f"Map saved -> {map_path}\n")

    import config as _cfg
    print("\n" + "="*60)
    print("   [OK] GEOSHIELD Training Pipeline Complete!")
    print("="*60)
    print(f"\n  [Data]     Cleaned Data -> {_cfg.CLEANED_DATA_PATH}")
    print(f"  [Map]      GIS Map      -> {map_path}")
    print(f"  [Reports]  Reports      -> {_cfg.REPORTS_DIR}")
    print(f"  [Alerts]   Alerts DB    -> {_cfg.ALERTS_DB_PATH}")
    print("\n  Launch Dashboard: streamlit run app/streamlit_app.py")
    print("  Launch API:       python app/api.py\n")


if __name__ == "__main__":
    main()
