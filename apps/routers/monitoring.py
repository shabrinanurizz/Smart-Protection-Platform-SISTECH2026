"""
Router untuk monitoring/metrics endpoint (skeleton).

Endpoint:
  GET /metrics

Berisi metrik dasar untuk observabilitas.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from apps.bootstrap.config import MODEL_CONFIG

router = APIRouter(
    tags=["Monitoring"],
)

_START_TIME = time.time()


@router.get("/metrics", summary="Get application metrics")
async def metrics() -> Dict[str, Any]:
    """
    Endpoint sederhana untuk metrics/monitoring.

    Catatan: Ini adalah skeleton. Untuk production-grade metrics,
    gunakan Prometheus integration dengan prometheus-fastapi-instrumentator
    atau library serupa.
    """
    from apps.services.model_service import ModelService

    model_version = "unknown"
    try:
        ms = ModelService.get_instance()
        model_version = ms.model_version
    except Exception:
        pass

    # Request count from log file
    requests_count = 0
    log_path = "logs/requests.jsonl"
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            requests_count = sum(1 for _ in f)

    predictions_count = 0
    pred_log = "logs/predictions.jsonl"
    if os.path.exists(pred_log):
        with open(pred_log, "r", encoding="utf-8") as f:
            predictions_count = sum(1 for _ in f)

    uptime_seconds = time.time() - _START_TIME

    return {
        "uptime_seconds": round(uptime_seconds, 2),
        "model_version": model_version,
        "model_name": MODEL_CONFIG.get("version", "unknown"),
        "requests_total": requests_count,
        "predictions_total": predictions_count,
        "status": "running",
    }


# ---------------------------------------------------------------------------
# Monitoring — drift history & active model performance
# ---------------------------------------------------------------------------
# drift_log.json & active_version.json berada di direktori parent dari
# registry_path (registry_path menunjuk ke model_registry/v1; drift log &
# active version ada di model_registry/). Path diselesaikan absolut via config.
_REGISTRY_DIR = Path(MODEL_CONFIG["registry_path"]).parent
_DRIFT_LOG_PATH = _REGISTRY_DIR / "drift_log.json"
_ACTIVE_VERSION_PATH = _REGISTRY_DIR / "active_version.json"
_METADATA_FILE = MODEL_CONFIG.get("metadata_file", "metadata.json")


def _read_drift_log() -> list[Dict[str, Any]]:
    """Baca riwayat monitoring drift dari ``drift_log.json``.

    Mengembalikan list kosong bila file belum ada.
    Me-raise ``json.JSONDecodeError`` bila JSON rusak dan ``ValueError`` bila
    strukturnya tidak valid (bukan list).
    """
    if not _DRIFT_LOG_PATH.exists():
        return []
    with open(_DRIFT_LOG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Format drift_log.json tidak valid: diharapkan list")
    return data


def _project_drift_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Proyek satu entri drift log ke format response yang konsisten."""
    performance = entry.get("performance") or {}
    distribution = entry.get("distribution") or {}
    return {
        "batch": entry.get("batch"),
        "active_version_before": entry.get("active_version_before"),
        "active_version_after": entry.get("active_version_after"),
        "performance": {
            "mae": performance.get("mae"),
            "performance_drift": performance.get("performance_drift"),
        },
        "distribution": {
            "distribution_drift": distribution.get("distribution_drift"),
            # ks_results hanya tersedia pada beberapa entri; null bila tidak ada
            "ks_results": distribution.get("ks_results"),
        },
        "drift_detected": entry.get("drift_detected"),
        "candidate_version": entry.get("candidate_version"),
        "promoted": entry.get("promoted"),
    }


def _read_active_version_metadata(version: str) -> Dict[str, Any]:
    """Baca ``metadata.json`` untuk sebuah versi model (tanpa load model.pkl)."""
    version_path = _REGISTRY_DIR / version
    metadata_path = version_path / _METADATA_FILE
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"metadata.json tidak ditemukan untuk versi '{version}'"
        )
    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    if not isinstance(meta, dict):
        raise ValueError(
            f"Format metadata.json versi '{version}' tidak valid: harus objek"
        )
    return meta


@router.get(
    "/monitoring/drift",
    summary="Get drift monitoring history",
    description=(
        "Membaca seluruh riwayat monitoring drift dari "
        "`model_registry/drift_log.json`. Jika file belum ada, mengembalikan "
        "list kosong (`[]`) beserta pesan yang sesuai."
    ),
    responses={
        200: {"description": "Berhasil memuat riwayat drift monitoring"},
        500: {"description": "Drift log rusak atau tidak valid"},
    },
)
async def get_drift_history() -> Dict[str, Any]:
    """Endpoint monitoring riwayat drift detection."""
    try:
        drift_log = _read_drift_log()
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Drift log rusak atau tidak valid (JSON): {e}",
        )
    except (ValueError, OSError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal memproses drift log: {e}",
        )

    records = [_project_drift_entry(entry) for entry in drift_log]

    if _DRIFT_LOG_PATH.exists():
        message = f"Berhasil memuat {len(records)} entri monitoring drift."
    else:
        message = (
            "Drift log belum tersedia (file tidak ditemukan). "
            "Belum ada monitoring drift yang dilakukan."
        )

    return {"data": records, "message": message}


@router.get(
    "/monitoring/model-performance",
    summary="Get active model performance metadata",
    description=(
        "Membaca `active_version.json`, lalu membaca `metadata.json` pada folder "
        "versi model aktif. Hanya metadata yang dibaca — `model.pkl` dan "
        "`encoding_maps.pkl` tidak pernah di-load."
    ),
    responses={
        200: {"description": "Berhasil memuat metadata model aktif"},
        404: {
            "description": "active_version.json atau metadata.json tidak ditemukan",
        },
        500: {"description": "File rusak atau tidak valid"},
    },
)
async def get_active_model_performance() -> Dict[str, Any]:
    """Endpoint monitoring performa model aktif (berbasis metadata saja)."""
    # 1. Baca active_version.json
    if not _ACTIVE_VERSION_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="active_version.json tidak ditemukan",
        )
    try:
        with open(_ACTIVE_VERSION_PATH, "r", encoding="utf-8") as f:
            active = json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"active_version.json rusak atau tidak valid (JSON): {e}",
        )
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal membaca active_version.json: {e}",
        )

    version = active.get("active_version")
    if not version:
        raise HTTPException(
            status_code=500,
            detail="active_version.json tidak mengandung field 'active_version'",
        )

    # 2. Baca metadata.json pada folder versi aktif (tanpa load model.pkl)
    try:
        meta = _read_active_version_metadata(version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"metadata.json versi '{version}' rusak atau tidak valid (JSON): {e}",
        )
    except (ValueError, OSError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal memproses metadata.json versi '{version}': {e}",
        )

    return {
        "active_version": version,
        "trained_at": meta.get("trained_at"),
        "metrics": meta.get("metrics"),
        "n_train_rows": meta.get("n_train_rows"),
        "trigger": meta.get("trigger"),
        "parent_version": meta.get("parent_version"),
        "feature_cols": meta.get("feature_cols"),
    }
