"""
Prediction controller: menangani HTTP request untuk risk prediction.

Controller bertugas sebagai jembatan antara router (HTTP) dan service (business logic).
Controller hanya melakukan:
- Validasi input (via Pydantic schema)
- Delegasi ke model service
- Mapping hasil ke response schema
- Logging prediction
"""

from __future__ import annotations

from typing import Any, Dict

from apps.schemas.prediction import PredictRiskRequest, PredictRiskResponse
from apps.services.model_service import ModelService


class PredictionController:
    """Controller untuk endpoint POST /predict-risk."""

    def __init__(self) -> None:
        self._model_service = ModelService.get_instance()

    def predict_risk(
        self,
        request: PredictRiskRequest,
    ) -> PredictRiskResponse:
        """
        Prediksi risk score berdasarkan lokasi + waktu.

        Args:
            request: PredictRiskRequest (lat, lon, hour, day)

        Returns:
            PredictRiskResponse (risk_score, risk_level)
        """
        risk_score, risk_level, info = self._model_service.predict(
            lat=request.lat,
            lon=request.lon,
            hour=request.hour,
            day=request.day,
        )

        # Log prediction
        from apps.bootstrap.logger import log_prediction
        log_prediction(
            risk_score=risk_score,
            risk_level=risk_level,
            input_features=info,
        )

        return PredictRiskResponse(
            risk_score=round(risk_score, 2),
            risk_level=risk_level,
        )
