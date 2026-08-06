"""
apps/routers/monitoring.py

Router untuk internal MLOps monitoring endpoints.

Endpoint:
    GET /metrics                        - metrik dasar aplikasi (uptime, request count, dst)
    GET /monitoring/drift                - deteksi data/prediction drift (PSI-based, sederhana)
    GET /monitoring/model-performance    - perbandingan performa antar versi model
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter

from apps.bootstrap.config import MODEL_CONFIG
from apps.schemas.monitoring import (
    DriftMetric,
    DriftReport,
    ModelPerformanceReport,
    ModelVersionPerformance,
)

router = APIRouter(tags=["Monitoring"])

_START_TIME = time.time()

REQUESTS_LOG = "logs/requests.jsonl"
PREDICTIONS_LOG = "logs/predictions.jsonl"

# PSI thresholds — rule of thumb yang umum dipakai industri untuk drift check
PSI_STABLE = 0.10
PSI_MODERATE = 0.25


# ------------------------------------------------------------------
# GET /metrics
# ------------------------------------------------------------------
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

    requests_count = _count_lines(REQUESTS_LOG)
    predictions_count = _count_lines(PREDICTIONS_LOG)
    uptime_seconds = time.time() - _START_TIME

    return {
        "uptime_seconds": round(uptime_seconds, 2),
        "model_version": model_version,
        "model_name": MODEL_CONFIG.get("version", "unknown"),
        "requests_total": requests_count,
        "predictions_total": predictions_count,
        "status": "running",
    }


# ------------------------------------------------------------------
# GET /monitoring/drift
# ------------------------------------------------------------------
@router.get(
    "/monitoring/drift",
    response_model=DriftReport,
    summary="Simple PSI-based drift check on recent predictions",
)
async def get_drift_report(window: int = 200) -> DriftReport:
    """
    Bandingkan distribusi risk_score & beberapa fitur numerik antara
    "baseline" (separuh AWAL dari `window` log prediksi terakhir) dan
    "current" (separuh TERBARU), menggunakan Population Stability Index (PSI).

    Ini adalah simplified drift detection, sesuai scope final project —
    bukan monitoring drift production-grade (yang biasanya butuh reference
    dataset training tersimpan terpisah, bukan cuma dari log prediksi).
    """
    records = _read_jsonl_tail(PREDICTIONS_LOG, limit=window)

    if len(records) < 20:
        return DriftReport(
            baseline_window="n/a",
            current_window="n/a",
            n_baseline=0,
            n_current=len(records),
            overall_status="insufficient_data",
            metrics=[],
            note=(
                f"Butuh minimal 20 baris di logs/predictions.jsonl untuk drift check, "
                f"baru ada {len(records)}. Coba hit POST /predict-risk/ lebih banyak dulu."
            ),
        )

    mid = len(records) // 2
    baseline = records[:mid]
    current = records[mid:]

    # Fitur numerik yang dicek — sesuaikan dengan feature vector model kalian
    fields_to_check = ["risk_score", "crime_count", "cell_freq_enc", "cell_target_enc"]
    metric_results: List[DriftMetric] = []
    worst_status = "stable"

    for field in fields_to_check:
        baseline_vals = _extract_field(baseline, field)
        current_vals = _extract_field(current, field)
        if not baseline_vals or not current_vals:
            continue
        psi = _population_stability_index(baseline_vals, current_vals)
        status = _psi_to_status(psi)
        metric_results.append(DriftMetric(feature=field, psi=round(psi, 4), status=status))
        if _status_rank(status) > _status_rank(worst_status):
            worst_status = status

    return DriftReport(
        baseline_window=f"log index 0-{mid - 1}",
        current_window=f"log index {mid}-{len(records) - 1}",
        n_baseline=len(baseline),
        n_current=len(current),
        overall_status=worst_status,
        metrics=metric_results,
    )


# ------------------------------------------------------------------
# GET /monitoring/model-performance
# ------------------------------------------------------------------
@router.get(
    "/monitoring/model-performance",
    response_model=ModelPerformanceReport,
    summary="Compare evaluation metrics across model versions",
)
async def get_model_performance() -> ModelPerformanceReport:
    """
    Baca metadata.json di setiap folder model_registry/<version>/ dan
    tampilkan metrik evaluasi (mae, rmse, r2, dst — sesuai yang disimpan
    saat training/versioning) side-by-side, supaya perkembangan model
    antar versi bisa ditelusuri (sesuai requirement Continual Learning
    di scoring criteria: "pencatatan versi model yang terdokumentasi").
    """
    from apps.services.model_service import ModelService

    registry_root = Path(MODEL_CONFIG["registry_path"]).parent
    metadata_file = MODEL_CONFIG.get("metadata_file", "metadata.json")

    active_version = "unknown"
    try:
        active_version = ModelService.get_instance().model_version
    except Exception:
        pass

    versions: List[ModelVersionPerformance] = []
    if registry_root.exists():
        for version_dir in sorted(registry_root.iterdir()):
            if not version_dir.is_dir():
                continue
            meta_path = version_dir / metadata_file
            if not meta_path.exists():
                continue
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            versions.append(
                ModelVersionPerformance(
                    version=version_dir.name,
                    is_active=(version_dir.name == active_version),
                    metrics=meta.get("metrics", {}),
                    trained_at=meta.get("trained_at") or meta.get("created_at"),
                )
            )

    return ModelPerformanceReport(active_version=active_version, versions=versions)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _count_lines(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def _read_jsonl_tail(path: str, limit: int) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    tail = lines[-limit:] if len(lines) > limit else lines
    records: List[Dict[str, Any]] = []
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _extract_field(records: List[Dict[str, Any]], field: str) -> List[float]:
    """Ambil nilai numerik `field` dari tiap record, cek di top-level dulu baru di record["input"]."""
    values: List[float] = []
    for r in records:
        if field in r:
            v = r[field]
        elif "input" in r and field in r["input"]:
            v = r["input"][field]
        else:
            continue
        try:
            values.append(float(v))
        except (TypeError, ValueError):
            continue
    return values


def _population_stability_index(baseline: List[float], current: List[float], bins: int = 10) -> float:
    """Hitung PSI antara dua distribusi numerik menggunakan quantile bins dari baseline."""
    if not baseline or not current:
        return 0.0

    sorted_baseline = sorted(baseline)
    quantile_edges = sorted(
        {
            sorted_baseline[int(q * (len(sorted_baseline) - 1))]
            for q in [i / bins for i in range(bins + 1)]
        }
    )
    if len(quantile_edges) < 3:
        return 0.0

    def bucketize(values: List[float]) -> List[int]:
        counts = [0] * (len(quantile_edges) - 1)
        for v in values:
            for i in range(len(quantile_edges) - 1):
                lo, hi = quantile_edges[i], quantile_edges[i + 1]
                is_last_bin = i == len(quantile_edges) - 2
                if (lo <= v <= hi) if is_last_bin else (lo <= v < hi):
                    counts[i] += 1
                    break
        return counts

    baseline_counts = bucketize(baseline)
    current_counts = bucketize(current)

    psi = 0.0
    eps = 1e-4
    for b_count, c_count in zip(baseline_counts, current_counts):
        b_pct = max(b_count / len(baseline), eps)
        c_pct = max(c_count / len(current), eps)
        psi += (c_pct - b_pct) * math.log(c_pct / b_pct)
    return abs(psi)


def _psi_to_status(psi: float) -> str:
    if psi < PSI_STABLE:
        return "stable"
    elif psi < PSI_MODERATE:
        return "moderate_shift"
    return "significant_shift"


def _status_rank(status: str) -> int:
    return {
        "stable": 0,
        "moderate_shift": 1,
        "significant_shift": 2,
        "insufficient_data": 0,
    }.get(status, 0)
