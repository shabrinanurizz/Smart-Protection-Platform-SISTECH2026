"""
train.py — Script untuk melatih & mengekspor model RandomForestRegressor
yang dipakai oleh API serving di api_serving2/.

Model ini dilatih HANYA pada 6 fitur yang tersedia saat serving time:
    lat_r, lon_r, dow_sin, dow_cos, hour_sin, hour_cos

Fitur `crime_count` dan `arrest_rate` disengaja DIKECUALIKAN karena tidak
tersedia untuk prediksi masa depan (lihat `excluded_features` di metadata.json).

Output:
    model_registry/v1/model.pkl       — model terlatih (joblib)
    model_registry/v1/metadata.json    — metadata terupdate dengan metrics akurat

Usage:
    cd api_serving2
    python train.py                  # pakai data/default path
    python train.py --data-path ../data/dataset/features_labels.csv
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error

# ---------------------------------------------------------------------
# Konstanta — HARUS konsisten dengan controller.py dan metadata.json
# ---------------------------------------------------------------------
FEATURE_COLS = [
    "lat_r",
    "lon_r",
    "dow_sin",
    "dow_cos",
    "hour_sin",
    "hour_cos",
]
TARGET_COL = "risk_score"
MODEL_VERSION = "v1"
RANDOM_STATE = 42

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "model_registry" / MODEL_VERSION

# Hyperparameter RandomForest — persis seperti di metadata.json (n_estimators=200,
# min_samples_leaf=1, max_features=1.0). Ini adalah spesifikasi model serving.
RF_PARAMS = {
    "n_estimators": 200,
    "max_depth": None,
    "min_samples_leaf": 1,
    "max_features": 1.0,
    "criterion": "squared_error",
    "random_state": RANDOM_STATE,
    "n_jobs": -1,
}


def load_data(data_path: Path) -> pd.DataFrame:
    """Load features_labels.csv."""
    if not data_path.exists():
        raise FileNotFoundError(
            f"Dataset tidak ditemukan di {data_path}. "
            f"Pastikan path benar (default: ../data/dataset/features_labels.csv)"
        )
    df = pd.read_csv(data_path)
    print(f"Dataset dimuat: {df.shape} baris, {len(df.columns)} kolom")

    missing = [c for c in FEATURE_COLS + [TARGET_COL] if c not in df.columns]
    if missing:
        raise ValueError(f"Kolom berikut tidak ditemukan di dataset: {missing}")

    return df


def train_model(df: pd.DataFrame) -> tuple[RandomForestRegressor, dict]:
    """Train RandomForestRegressor dan return model + metrics."""
    X = df[FEATURE_COLS]
    y = df[TARGET_COL]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE
    )

    print(f"Train: {X_train.shape} | Test: {X_test.shape}")

    model = RandomForestRegressor(**RF_PARAMS)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2 = float(1 - np.sum((y_test - y_pred) ** 2) / np.sum((y_test - y_test.mean()) ** 2))

    metrics = {"mae_test": round(mae, 4), "rmse_test": round(rmse, 4), "r2_test": round(r2, 4)}
    print(f"Metrics: MAE={mae:.4f}  RMSE={rmse:.4f}  R2={r2:.4f}")

    return model, metrics


def compute_risk_thresholds(y_train: np.ndarray) -> tuple[float, float]:
    """Hitung Low/Medium/High thresholds dari kuartil 33%/67% risk_score training set."""
    low_max = float(np.percentile(y_train, 33.33))
    high_min = float(np.percentile(y_train, 66.67))
    return round(low_max, 1), round(high_min, 1)


def save_model_and_metadata(model, metrics: dict, y_train: np.ndarray):
    """Simpan model.pkl dan metadata.json."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODEL_DIR / "model.pkl"
    joblib.dump(model, model_path)
    print(f"Model disimpan: {model_path}")

    low_max, high_min = compute_risk_thresholds(y_train)

    metadata = {
        "version": MODEL_VERSION,
        "algorithm": "RandomForestRegressor",
        "params": {
            "bootstrap": True,
            "ccp_alpha": 0.0,
            "criterion": RF_PARAMS["criterion"],
            "max_depth": RF_PARAMS["max_depth"],
            "max_features": RF_PARAMS["max_features"],
            "max_leaf_nodes": None,
            "max_samples": None,
            "min_impurity_decrease": 0.0,
            "min_samples_leaf": RF_PARAMS["min_samples_leaf"],
            "min_samples_split": 2,
            "min_weight_fraction_leaf": 0.0,
            "monotonic_cst": None,
            "n_estimators": RF_PARAMS["n_estimators"],
            "n_jobs": RF_PARAMS["n_jobs"],
            "oob_score": False,
            "random_state": RF_PARAMS["random_state"],
            "verbose": 0,
            "warm_start": False,
        },
        "feature_cols": FEATURE_COLS,
        "metrics": metrics,
        "risk_level_thresholds": {
            "low_max": low_max,
            "high_min": high_min,
            "method": "tertile (kuantil 33%/67%) dari risk_score training set",
        },
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "source_dataset": "features_labels.csv (output CP1)",
        "excluded_features": {
            "crime_count": "tidak tersedia saat serving untuk waktu yang belum terjadi",
            "arrest_rate": "tidak tersedia saat serving untuk waktu yang belum terjadi",
        },
        "note": (
            "Model ini dilatih HANYA pada 6 fitur yang tersedia saat inference "
            "(lat_r, lon_r, dow_sin, dow_cos, hour_sin, hour_cos). "
            "crime_count dan arrest_rate dikecualikan karena sifatnya yang post-hoc."
        ),
    }

    metadata_path = MODEL_DIR / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Metadata disimpan: {metadata_path}")


def main():
    parser = argparse.ArgumentParser(description="Train & export Risk Score model")
    parser.add_argument(
        "--data-path",
        type=Path,
        default=BASE_DIR.parent / "data" / "dataset" / "features_labels.csv",
        help="Path ke features_labels.csv",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("TRAINING RISIKO SCORE MODEL (RandomForestRegressor)")
    print("=" * 60)
    print(f"Feature cols : {FEATURE_COLS}")
    print(f"Params       : {RF_PARAMS}")
    print(f"Data path    : {args.data_path}")
    print(f"Model dir    : {MODEL_DIR}")
    print()

    df = load_data(args.data_path)

    X = df[FEATURE_COLS]
    y = df[TARGET_COL].values
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE
    )

    model, metrics = train_model(df)
    save_model_and_metadata(model, metrics, y_train)

    print("\n" + "=" * 60)
    print("TRAINING SELESAI ✅")
    print(f"  model.pkl         → {MODEL_DIR / 'model.pkl'}")
    print(f"  metadata.json     → {MODEL_DIR / 'metadata.json'}")
    print(f"  MAE test          : {metrics['mae_test']}")
    print(f"  RMSE test         : {metrics['rmse_test']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
