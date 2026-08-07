"""
apps/schemas/model_info.py

Pydantic schema untuk GET /model/info.

Response:
{
  "model_name": "RandomForestRegressor",
  "model_version": "v1",
  "feature_names": ["lat_r", "lon_r", ...],
  "registry_path": "model_registry/v1",
  "loaded_at": "2026-08-05T09:12:00+00:00",
  "metadata": {...},
  "model_params": {"n_estimators": 200, "max_depth": 12, ...}
}
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ModelInfoResponse(BaseModel):
    """Response body untuk endpoint GET /model/info."""

    model_name: str = Field(..., description="Nama/tipe model (e.g. RandomForestRegressor)")
    model_version: str = Field(..., description="Versi model yang sedang aktif di-serve")
    feature_names: List[str] = Field(
        default_factory=list, description="Urutan fitur yang dipakai model saat inference"
    )
    registry_path: str = Field(..., description="Path folder model di model_registry/")
    loaded_at: Optional[str] = Field(
        None, description="Timestamp (ISO 8601) saat model di-load ke memori"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Isi metadata.json apa adanya (versioning info)"
    )
    model_params: Dict[str, Any] = Field(
        default_factory=dict, description="Hyperparameter model (best-effort, jika tersedia)"
    )
