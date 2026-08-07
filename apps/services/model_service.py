"""
Model service: loading model, preprocessing input, inference, dan risk-level mapping.

Model: RandomForestRegressor yang dilatih di notebooks/Modelling-Train.ipynb
- Disimpan di model_registry/v1/model.pkl (via joblib)
- 9 features: lat_r, lon_r, hour_sin, hour_cos, dow_sin, dow_cos,
  crime_count, cell_freq_enc, cell_target_enc
- Target: risk_score (0-100)

Preprocessing harus IDENTIK dengan training:
1. Round lat/lon ke 2 desimal → lat_r, lon_r
2. cell_id = f"{lat_r}_{lon_r}"
3. hour_sin/cos = sin/cos(2π·hour/24)
4. dow_sin/cos = sin/cos(2π·dow/7)
5. dow = konversi nama hari → angka (Mon=0, Sun=6)
6. crime_count = lookup rata-rata per cell_id dari dataset
7. cell_freq_enc = freq_map[cell_id] (value_counts(normalize=True) dari train_df)
8. cell_target_enc = target_map[cell_id] (groupby(cell_id).mean() dari train_df)

Encoding maps (freq_map, target_map, global_fallback) dihitung dari
features_labels.csv dengan train_test_split(test_size=0.2, random_state=42)
yang SAMA persis dengan training notebook.

Model dan encoding maps di-load SEKALI pada startup (singleton).
"""

from __future__ import annotations

import json
import os
import bz2
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from apps.bootstrap.config import (
    DAY_MAPPING,
    LOCATION_ROUNDING,
    MODEL_CONFIG,
    RISK_THRESHOLDS,
)


class ModelService:
    """
    Service untuk model risk prediction.

    Bertanggung jawab untuk:
    - Loading model (singleton, di-load sekali pada startup)
    - Mempersiapkan encoding maps (freq_map, target_map, global_mean) dari dataset
    - Preprocessing input request → feature vector yang konsisten dengan training
    - Inference menggunakan model
    - Konversi risk_score → risk_level berdasarkan threshold
    - Model version management
    """

    def __init__(self) -> None:
        self._model: Optional[Any] = None
        self._metadata: Optional[Dict[str, Any]] = None
        self._feature_names: Optional[list[str]] = None

        # Encoding maps (dihitung dari dataset training split)
        self._freq_map: Optional[pd.Series] = None
        self._target_map: Optional[pd.Series] = None
        self._global_mean: float = 0.0

        # Lookup crime_count per cell_id (rata-rata dari dataset)
        self._crime_count_map: Optional[Dict[str, float]] = None
        self._global_crime_count: float = 0.0

        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def load(self) -> None:
        """Load model + encoding maps. Dipanggil sekali pada startup."""
        registry_path = Path(MODEL_CONFIG["registry_path"])
        model_file = MODEL_CONFIG["model_file"]
        metadata_file = MODEL_CONFIG["metadata_file"]

        model_path = registry_path / model_file
        metadata_path = registry_path / metadata_file

        # --- Load model ---
        if not model_path.exists():
            raise FileNotFoundError(f"Model file tidak ditemukan: {model_path}")
        with bz2.BZ2File(str(model_path), "rb") as f:
            self._model = joblib.load(f)

        # --- Load metadata ---
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                self._metadata = json.load(f)
        else:
            self._metadata = {}

        # --- Get feature names from model ---
        if hasattr(self._model, "feature_names_in_"):
            self._feature_names = list(self._model.feature_names_in_)
        elif "features" in self._metadata:
            self._feature_names = self._metadata["features"]
        else:
            raise RuntimeError("Tidak dapat menentukan feature names dari model atau metadata")

        # --- Build encoding maps dari dataset ---
        self._build_encoding_maps()

        self._initialized = True

    def _build_encoding_maps(self) -> None:
        """
        Bangun freq_map, target_map, dan crime_count_map dari dataset
        dengan train_test_split yang SAMA seperti training notebook
        (test_size=0.2, random_state=42).
        """
        from apps.bootstrap.config import DATASET_CONFIG

        dataset_path = DATASET_CONFIG.get("path")
        if not dataset_path or not Path(dataset_path).exists():
            raise FileNotFoundError(
                f"Dataset tidak ditemukan di: {dataset_path}. "
                "Diperlukan untuk encoding maps (cell_freq_enc, cell_target_enc)."
            )

        df = pd.read_csv(dataset_path)

        # Split yang sama persis dengan training notebook
        train_df, _ = train_test_split(df, test_size=0.2, random_state=42)
        train_df = train_df.reset_index(drop=True)

        # freq_map: value_counts(normalize=True) per cell_id
        self._freq_map = train_df["cell_id"].value_counts(normalize=True)

        # target_map: mean risk_score per cell_id
        self._target_map = train_df.groupby("cell_id")["risk_score"].mean()

        # global_mean: fallback untuk cell_target_enc
        self._global_mean = float(train_df["risk_score"].mean())

        # crime_count_map: rata-rata crime_count per cell_id (dari seluruh dataset)
        self._crime_count_map = (
            df.groupby("cell_id")["crime_count"].mean().to_dict()
        )
        self._global_crime_count = float(df["crime_count"].mean())

    # ------------------------------------------------------------------
    # Preprocessing (harus IDENTIK dengan notebook training)
    # ------------------------------------------------------------------
    def _parse_day(self, day: str) -> int:
        """Konversi nama hari → angka (Monday=0, Sunday=6)."""
        normalized = day.strip().lower()
        if normalized not in DAY_MAPPING:
            raise ValueError(f"Day '{day}' tidak valid. Gunakan: {', '.join(DAY_MAPPING.keys())}")
        return DAY_MAPPING[normalized]

    def _preprocess(
        self,
        lat: float,
        lon: float,
        hour: int,
        day: str,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Preprocess input request → feature vector DataFrame
        dengan urutan kolom yang sama persis seperti model training.

        Returns:
            (X, info) — X adalah DataFrame dengan 1 row, info berisi debug data.
        """
        if not self._initialized:
            raise RuntimeError("Model belum di-load. Panggil load() terlebih dahulu.")

        # 1. Round lat/lon → lat_r, lon_r
        lat_r = round(lat, LOCATION_ROUNDING)
        lon_r = round(lon, LOCATION_ROUNDING)

        # 2. cell_id
        cell_id = f"{lat_r}_{lon_r}"

        # 3-4. Cyclical encoding
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)

        dow = self._parse_day(day)
        dow_sin = np.sin(2 * np.pi * dow / 7)
        dow_cos = np.cos(2 * np.pi * dow / 7)

        # 5. crime_count lookup (average per cell_id)
        crime_count = self._crime_count_map.get(cell_id, self._global_crime_count)

        # 6. cell_freq_enc lookup
        freq_val = self._freq_map.get(cell_id, 0.0)
        cell_freq_enc = float(freq_val) if not pd.isna(freq_val) else 0.0

        # 7. cell_target_enc lookup
        target_val = self._target_map.get(cell_id, self._global_mean)
        cell_target_enc = float(target_val) if not pd.isna(target_val) else self._global_mean

        # Build feature vector dalam urutan yang sama persis dengan model training
        feature_row = {
            "lat_r": lat_r,
            "lon_r": lon_r,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "dow_sin": dow_sin,
            "dow_cos": dow_cos,
            "crime_count": crime_count,
            "cell_freq_enc": cell_freq_enc,
            "cell_target_enc": cell_target_enc,
        }

        # Pastikan urutan kolom sesuai model.feature_names_in_
        X = pd.DataFrame([feature_row], columns=self._feature_names)

        info = {
            "cell_id": cell_id,
            "lat_r": lat_r,
            "lon_r": lon_r,
            "dow": dow,
            "hour": hour,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "dow_sin": dow_sin,
            "dow_cos": dow_cos,
            "crime_count": crime_count,
            "cell_freq_enc": cell_freq_enc,
            "cell_target_enc": cell_target_enc,
            "global_mean": self._global_mean,
            "global_crime_count": self._global_crime_count,
        }

        return X, info

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def predict(
        self,
        lat: float,
        lon: float,
        hour: int,
        day: str,
    ) -> Tuple[float, str, Dict[str, Any]]:
        """
        Prediksi risk score untuk satu lokasi + waktu.

        Returns:
            (risk_score, risk_level, info)
        """
        X, info = self._preprocess(lat, lon, hour, day)
        risk_score = float(self._model.predict(X)[0])

        # Clamp ke range 0-100
        risk_score = max(0.0, min(100.0, risk_score))

        risk_level = self._score_to_level(risk_score)

        return risk_score, risk_level, info

    def predict_batch(
        self,
        coordinates: list[Tuple[float, float, int, str]],
    ) -> list[Tuple[float, str, Dict[str, Any]]]:
        """Prediksi risk score untuk multiple lokasi sekaligus."""
        results = []
        for lat, lon, hour, day in coordinates:
            results.append(self.predict(lat, lon, hour, day))
        return results

    # ------------------------------------------------------------------
    # Risk level mapping
    # ------------------------------------------------------------------
    def _score_to_level(self, score: float) -> str:
        """Konversi risk_score → risk_level berdasarkan threshold di config.yaml."""
        low_max = float(os.environ.get("RISK_LOW_MAX", RISK_THRESHOLDS.get("low_max", 33.0)))
        medium_max = float(os.environ.get("RISK_MEDIUM_MAX", RISK_THRESHOLDS.get("medium_max", 66.0)))

        if score <= low_max:
            return "Low"
        elif score <= medium_max:
            return "Medium"
        else:
            return "High"

    # ------------------------------------------------------------------
    # Metadata / version
    # ------------------------------------------------------------------
    @property
    def feature_names(self) -> list[str]:
        if self._feature_names is None:
            raise RuntimeError("Model belum di-load")
        return self._feature_names

    @property
    def metadata(self) -> Dict[str, Any]:
        return self._metadata or {}

    @property
    def model_version(self) -> str:
        return self._metadata.get("version", "unknown") if self._metadata else "unknown"

    @property
    def model_name(self) -> str:
        return self._metadata.get("model_name", "unknown") if self._metadata else "unknown"

    # ------------------------------------------------------------------
    # Singleton pattern
    # ------------------------------------------------------------------
    _instance: Optional["ModelService"] = None

    @classmethod
    def get_instance(cls) -> "ModelService":
        """Get singleton instance. Load otomatis jika belum di-load."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load()
        return cls._instance

