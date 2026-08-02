"""
Bootstrap configuration: loads config.yaml dan environment variables (.env).

Semua nilai non-secret dikelola di config.yaml.
Secret values (API keys, dll) di-load dari environment variables via python-dotenv
atau secara manual jika dotenv tidak tersedia.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

# Project root = dua level di atas folder ini (apps/bootstrap/config.py → project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load .env jika ada (hanya untuk secret values, bukan config.yaml)
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)


def _resolve_path(*parts: str) -> Path:
    """Resolve relative path from project root."""
    return PROJECT_ROOT.joinpath(*parts)


def load_config(config_file: str = "config.yaml") -> Dict[str, Any]:
    """Load dan parse config.yaml menjadi dictionary."""
    config_path = PROJECT_ROOT / config_file
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file tidak ditemukan: {config_path}"
        )
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Resolve dataset path relative to project root
    if "dataset" in config:
        ds_path = config["dataset"].get("path", "")
        if ds_path and not os.path.isabs(ds_path):
            config["dataset"]["path"] = str(_resolve_path(ds_path))

    # Resolve model paths
    if "model" in config:
        reg_path = config["model"].get("registry_path", "")
        if reg_path and not os.path.isabs(reg_path):
            config["model"]["registry_path"] = str(_resolve_path(reg_path))

    # Resolve log paths
    if "logging" in config:
        for key in ("requests_log", "predictions_log", "errors_log"):
            log_path = config["logging"].get(key, "")
            if log_path and not os.path.isabs(log_path):
                config["logging"][key] = str(_resolve_path(log_path))

    return config


# Singleton config instance (loaded once at import)
CONFIG: Dict[str, Any] = load_config()

# Convenience accessors
RISK_THRESHOLDS: Dict[str, float] = CONFIG.get("risk_thresholds", {})
MODEL_CONFIG: Dict[str, Any] = CONFIG.get("model", {})
ROUTING_CONFIG: Dict[str, Any] = CONFIG.get("routing", {})
DATASET_CONFIG: Dict[str, Any] = CONFIG.get("dataset", {})
LOG_CONFIG: Dict[str, Any] = CONFIG.get("logging", {})
ROUTE_SCORING_CONFIG: Dict[str, Any] = CONFIG.get("route_scoring", {})
DAY_MAPPING: Dict[str, int] = CONFIG.get("day_mapping", {})
LOCATION_ROUNDING: int = CONFIG.get("location_rounding", 2)


def get_env(key: str, default: str | None = None) -> str:
    """Get environment variable (dari .env yang sudah di-load)."""
    return os.environ.get(key, default) if default is not None else os.environ[key]
