"""
Router untuk Risk Prediction endpoint.

Endpoint:
  POST /predict-risk
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from apps.controllers.prediction_controller import PredictionController
from apps.schemas.prediction import PredictRiskRequest, PredictRiskResponse

router = APIRouter(
    prefix="/predict-risk",
    tags=["Prediction"],
)

# Controller instance (singleton via ModelService)
_controller = PredictionController()


@router.post(
    "/",
    response_model=PredictRiskResponse,
    summary="Predict crime/safety risk score",
    description=(
        "Menerima lokasi (lat/lon) + waktu (hour/day) dan mengembalikan "
        "risk_score (0-100) serta risk_level (Low/Medium/High)."
    ),
    responses={
        200: {"description": "Berhasil memprediksi risk score",
              "content": {"application/json": {
                  "example": {"risk_score": 62.58, "risk_level": "Medium"}}}},
        400: {"description": "Input tidak valid (latitude/longitude/hour/day)"},
        422: {"description": "Validasi gagal (field kosong atau tipe salah)"},
        500: {"description": "Internal server error"},
    },
)
async def predict_risk(
    request: Request,
    payload: PredictRiskRequest,
) -> PredictRiskResponse:
    """
    Prediksi risk score berdasarkan lokasi dan waktu.

    **Contoh request:**
    ```json
    {
      "lat": -6.2,
      "lon": 106.8,
      "hour": 22,
      "day": "Saturday"
    }
    ```

    **Contoh response:**
    ```json
    {
      "risk_score": 62.58,
      "risk_level": "Medium"
    }
    ```
    """
    try:
        result = _controller.predict_risk(payload)
        return result
    except FileNotFoundError as e:
        from apps.bootstrap.logger import log_error
        log_error(
            error_type="FileNotFoundError",
            message=str(e),
            path="/predict-risk",
            request_id=getattr(request.state, "request_id", None),
        )
        raise HTTPException(
            status_code=503,
            detail="Model atau dataset tidak tersedia. Hubungi administrator.",
        )
    except Exception as e:
        from apps.bootstrap.logger import log_error
        log_error(
            error_type=type(e).__name__,
            message=str(e),
            path="/predict-risk",
            request_id=getattr(request.state, "request_id", None),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {type(e).__name__}",
        )
