"""
Controller -- logic yang jalan saat request masuk: load artifact dari
registry, ubah (lat, lon, datetime) mentah jadi 6 fitur yang dipakai model
(persis feature_cols di notebook CP2), lalu panggil model.predict().

Ini bagian yang di materi Session 3 disebut "Controller": logic murni,
terpisah dari router (yang cuma urusan routing HTTP).
"""

import json
import math
from datetime import datetime
from pathlib import Path

import joblib

# --------------------------------------------------------------------------
# Bounding box Jabodetabek (proxy), persis dari README CP1.
# Di luar rentang ini, API menolak request -- lihat catatan poin (d) yang
# perlu didiskusikan dengan FE: apakah error 400 ini sudah sesuai ekspektasi
# mereka, atau mereka butuh perilaku lain (mis. fallback ke skor 0).
# --------------------------------------------------------------------------
LAT_MIN, LAT_MAX = -6.55, -6.10
LON_MIN, LON_MAX = 106.55, 107.05

# Harus sama persis dengan ROUND_DECIMALS di notebook CP1 (grid ~1km/sel).
# Kalau CP1 mengubah angka ini di iterasi berikutnya, angka ini WAJIB ikut
# diubah, karena sel yang dipakai model belajar dan sel yang dipakai API
# harus konsisten.
ROUND_DECIMALS = 2


class OutOfBoundsError(ValueError):
    """Dilempar kalau lat/lon di luar bounding box Jabodetabek yang didukung."""


class InvalidDatetimeError(ValueError):
    """Dilempar kalau string datetime tidak bisa di-parse sebagai ISO 8601."""


def _cyclical_encode(value: int, period: int) -> tuple[float, float]:
    """sin/cos encoding -- identik dengan cyclical_encode() di notebook CP1."""
    angle = 2 * math.pi * value / period
    return math.sin(angle), math.cos(angle)


def validate_bounds(lat: float, lon: float) -> None:
    if not (LAT_MIN <= lat <= LAT_MAX) or not (LON_MIN <= lon <= LON_MAX):
        raise OutOfBoundsError(
            f"Koordinat ({lat}, {lon}) di luar area yang didukung "
            f"(lat {LAT_MIN}..{LAT_MAX}, lon {LON_MIN}..{LON_MAX})"
        )


def parse_datetime(dt_str: str) -> datetime:
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError as e:
        raise InvalidDatetimeError(
            f"Format datetime tidak valid: '{dt_str}'. Gunakan ISO 8601, "
            f"contoh: 2026-08-02T14:00:00"
        ) from e


def build_feature_vector(lat: float, lon: float, dt: datetime) -> dict:
    """
    Susun 6 fitur persis sesuai feature_cols di notebook CP2:
    lat_r, lon_r, dow_sin, dow_cos, hour_sin, hour_cos.

    dow mengikuti pandas/Python convention: Monday=0 ... Sunday=6 (dt.weekday()).
    Kalau CP1 memakai konvensi lain untuk dow, ini WAJIB disamakan --
    kalau tidak, model akan menerima fitur yang salah maknanya walau
    bentuknya (angka sin/cos) tetap valid secara numerik.
    """
    lat_r = round(lat, ROUND_DECIMALS)
    lon_r = round(lon, ROUND_DECIMALS)

    dow_sin, dow_cos = _cyclical_encode(dt.weekday(), 7)
    hour_sin, hour_cos = _cyclical_encode(dt.hour, 24)

    return {
        "lat_r": lat_r,
        "lon_r": lon_r,
        "dow_sin": dow_sin,
        "dow_cos": dow_cos,
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
    }


class RiskModelRegistry:
    """
    Load model + metadata sekali saat startup (bukan tiap request -- lebih
    cepat, dan menghindari race condition baca file). Kalau CP3 nanti nambah
    versi baru (v2, v3, ...), cukup ganti `version` di sini atau baca dari
    config -- tidak perlu ubah kode registry ini.
    """

    def __init__(self, registry_dir: str | Path, version: str = "v1"):
        self.registry_dir = Path(registry_dir)
        self.version = version
        self._version_dir = self.registry_dir / version

        model_path = self._version_dir / "model.pkl"
        metadata_path = self._version_dir / "metadata.json"

        if not model_path.exists():
            raise FileNotFoundError(f"Model tidak ditemukan: {model_path}")
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata tidak ditemukan: {metadata_path}")

        self.model = joblib.load(model_path)
        with open(metadata_path) as f:
            self.metadata = json.load(f)

        self.feature_cols: list[str] = self.metadata["feature_cols"]
        thresholds = self.metadata["risk_level_thresholds"]
        self.low_max: float = thresholds["low_max"]
        self.high_min: float = thresholds["high_min"]

    def risk_level(self, score: float) -> str:
        if score < self.low_max:
            return "Low"
        elif score <= self.high_min:
            return "Medium"
        else:
            return "High"

    def predict(self, lat: float, lon: float, dt_str: str) -> dict:
        validate_bounds(lat, lon)
        dt = parse_datetime(dt_str)
        features = build_feature_vector(lat, lon, dt)

        # Urutan kolom HARUS sama dengan urutan feature_cols saat training --
        # ini kenapa kita bangun dict lalu ambil sesuai self.feature_cols,
        # bukan sekadar list(features.values()).
        ordered = [[features[col] for col in self.feature_cols]]
        raw_score = float(self.model.predict(ordered)[0])
        score = max(0.0, min(100.0, raw_score))  # jaga-jaga clip ke rentang 0-100

        return {
            "risk_score": round(score, 2),
            "level": self.risk_level(score),
            "model_version": self.metadata["version"],
            "last_updated": self.metadata["trained_at"],
        }
