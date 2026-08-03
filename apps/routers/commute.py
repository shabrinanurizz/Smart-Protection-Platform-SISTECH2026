"""
Router untuk Safe Commute endpoint.

Endpoint:
  POST /safe-commute
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from apps.controllers.commute_controller import CommuteController
from apps.schemas.commute import SafeCommuteRequest, SafeCommuteResponse

router = APIRouter(
    prefix="/safe-commute",
    tags=["Safe Commute"],
)

# Controller instance
_controller = CommuteController()


@router.post(
    "/",
    response_model=SafeCommuteResponse,
    summary="Plan a safe commute route",
    description=(
        "Menerima titik awal, tujuan, waktu, dan hari. "
        "Mengembalikan rekomendasi rute, jarak, durasi, route risk score, "
        "dan risk level."
    ),
    responses={
        200: {"description": "Berhasil merencanakan safe commute"},
        400: {"description": "Input tidak valid"},
        422: {"description": "Validasi gagal"},
        503: {"description": "Model atau routing service tidak tersedia"},
        500: {"description": "Internal server error"},
    },
)
async def safe_commute(
    request: Request,
    payload: SafeCommuteRequest,
) -> SafeCommuteResponse:
    """
    Rencanakan safe commute dari titik awal ke tujuan.

    **Contoh request:**
    ```json
    {
      "start": {"lat": -6.2, "lon": 106.8},
      "destination": {"lat": -6.21, "lon": 106.82},
      "hour": 22,
      "day": "Saturday"
    }
    ```

    **Contoh response:**
    ```json
    {
      "route": [[-6.2, 106.8], [-6.205, 106.81]],
      "distance_meters": 2200.0,
      "duration_seconds": 300.0,
      "route_risk_score": 65.3,
      "risk_level": "Medium",
      "segment_risks": [...],
      "recommendation": "...",
      "routing_provider": "osrm"
    }
    ```
    """
    try:
        result = _controller.plan_commute(payload)
        return result
    except FileNotFoundError as e:
        from apps.bootstrap.logger import log_error
        log_error(
            error_type="FileNotFoundError",
            message=str(e),
            path="/safe-commute",
            request_id=getattr(request.state, "request_id", None),
        )
        raise HTTPException(
            status_code=503,
            detail=f"Resource tidak tersedia: {e}",
        )
    except Exception as e:
        from apps.bootstrap.logger import log_error
        log_error(
            error_type=type(e).__name__,
            message=str(e),
            path="/safe-commute",
            request_id=getattr(request.state, "request_id", None),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {type(e).__name__}",
        )
