"""
apps/routers/model.py

Router untuk informasi model yang SEDANG AKTIF (currently loaded in memory
by the running FastAPI process via ModelService singleton).

Endpoint:
    GET /model/info

Beda dengan GET /registry/{version} (yang membaca metadata.json langsung
dari disk untuk SEMUA versi yang ada di model_registry/), endpoint ini
khusus menunjukkan versi yang benar-benar dipakai untuk serving prediksi
saat ini — berguna untuk internal MLOps sanity-check ("model mana sih yang
lagi live sekarang?") tanpa perlu buka file config.yaml.
"""
from __future__ import annotations

from fastapi import APIRouter

from apps.bootstrap.config import MODEL_CONFIG
from apps.schemas.model_info import ModelInfoResponse
from apps.services.model_service import ModelService

router = APIRouter(prefix="/model", tags=["Registry"])


@router.get(
    "/info",
    response_model=ModelInfoResponse,
    summary="Get info of the model currently loaded for serving",
)
async def get_model_info() -> ModelInfoResponse:
    """Kembalikan detail model yang sedang di-load oleh ModelService singleton."""
    ms = ModelService.get_instance()

    # Best-effort ambil hyperparameter model (kalau model-nya sklearn-like)
    model_params: dict = {}
    try:
        raw_model = getattr(ms, "_model", None)
        if raw_model is not None and hasattr(raw_model, "get_params"):
            model_params = {
                k: v
                for k, v in raw_model.get_params().items()
                if isinstance(v, (str, int, float, bool, type(None)))
            }
    except Exception:
        # Model bukan sklearn-estimator biasa, atau ada param yang enggak serializable — skip aja
        model_params = {}

    return ModelInfoResponse(
        model_name=ms.model_name,
        model_version=ms.model_version,
        feature_names=ms.feature_names,
        registry_path=str(MODEL_CONFIG.get("registry_path", "")),
        loaded_at=getattr(ms, "loaded_at", None),
        metadata=ms.metadata,
        model_params=model_params,
    )
