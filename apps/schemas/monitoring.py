"""
apps/schemas/monitoring.py

Pydantic schemas untuk internal MLOps monitoring endpoints:
    GET /monitoring/drift
    GET /monitoring/model-performance
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------
# GET /monitoring/drift
# -----------------------------------------------------------------------
class DriftMetric(BaseModel):
    """Hasil PSI check untuk satu fitur."""

    feature: str = Field(..., description="Nama fitur yang dicek driftnya")
    psi: float = Field(..., description="Population Stability Index (semakin besar, semakin drift)")
    status: str = Field(
        ..., description="stable | moderate_shift | significant_shift"
    )


class DriftReport(BaseModel):
    """Response body untuk GET /monitoring/drift."""

    baseline_window: str = Field(..., description="Rentang log yang dipakai sebagai baseline")
    current_window: str = Field(..., description="Rentang log terbaru yang dibandingkan")
    n_baseline: int = Field(..., description="Jumlah data pada window baseline")
    n_current: int = Field(..., description="Jumlah data pada window current")
    overall_status: str = Field(
        ..., description="Status drift paling parah dari semua fitur yang dicek"
    )
    metrics: List[DriftMetric] = Field(default_factory=list)
    note: Optional[str] = Field(None, description="Catatan tambahan (e.g. data belum cukup)")


# -----------------------------------------------------------------------
# GET /monitoring/model-performance
# -----------------------------------------------------------------------
class ModelVersionPerformance(BaseModel):
    """Metrik evaluasi untuk satu versi model."""

    version: str = Field(..., description="Nama versi (e.g. v1, v2, v3)")
    is_active: bool = Field(..., description="Apakah versi ini yang sedang dipakai serving")
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metrik evaluasi yang disimpan di metadata.json saat training (mae, rmse, r2, dst)",
    )
    trained_at: Optional[str] = Field(None, description="Timestamp kapan versi ini di-training")


class ModelPerformanceReport(BaseModel):
    """Response body untuk GET /monitoring/model-performance."""

    active_version: str = Field(..., description="Versi model yang sedang di-serve saat ini")
    versions: List[ModelVersionPerformance] = Field(default_factory=list)
