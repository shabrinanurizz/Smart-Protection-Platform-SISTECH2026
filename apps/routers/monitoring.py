"""
Router untuk monitoring/metrics endpoint (skeleton).

Endpoint:
  GET /metrics

Berisi metrik dasar untuk observabilitas.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi import APIRouter

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
