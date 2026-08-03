"""
Router untuk health check endpoint.

Endpoint:
  GET /health
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter

from apps.services.model_service import ModelService

router = APIRouter(
    tags=["Health"],
)


@router.get(
    "/health",
    summary="Health check",
    description="Memeriksa apakah API dan model siap menerima permintaan.",
    responses={
        200: {"description": "Service sehat"},
        503: {"description": "Service tidak siap (model belum dimuat)"},
    },
)
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    from apps.services.routing_service import RoutingService

    model_ok = False
    model_info: Dict[str, Any] = {}

    try:
        ms = ModelService.get_instance()
        model_ok = ms._initialized
        if model_ok:
            model_info = {
                "model_name": ms.model_name,
                "version": ms.model_version,
                "features": ms.feature_names,
            }
    except Exception as e:
        model_info = {"error": str(e)}

    routing_ok = False
    routing_info: Dict[str, Any] = {}
    try:
        rs = RoutingService.get_instance()
        routing_ok = True
        routing_info = {"provider": rs.provider_name}
    except Exception as e:
        routing_info = {"error": str(e)}

    overall_ok = model_ok and routing_ok

    return {
        "status": "healthy" if overall_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "model": {
                "status": "ok" if model_ok else "error",
                **model_info,
            },
            "routing": {
                "status": "ok" if routing_ok else "error",
                **routing_info,
            },
        },
    }
