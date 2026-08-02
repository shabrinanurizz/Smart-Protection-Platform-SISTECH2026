"""
Router untuk model registry endpoint.

Endpoint:
  GET /registry
  GET /registry/{version}

Menampilkan informasi model yang terdaftar di model_registry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from apps.bootstrap.config import MODEL_CONFIG

router = APIRouter(
    prefix="/registry",
    tags=["Registry"],
)


@router.get("/", summary="List all registered models")
async def list_models() -> List[Dict[str, Any]]:
    """List semua model yang tersedia di model_registry."""
    registry_path = Path(MODEL_CONFIG["registry_path"])
    if not registry_path.exists():
        raise HTTPException(status_code=404, detail="Model registry directory tidak ditemukan")

    models = []
    for version_dir in sorted(registry_path.iterdir()):
        if not version_dir.is_dir():
            continue
        metadata_path = version_dir / MODEL_CONFIG.get("metadata_file", "metadata.json")
        model_path = version_dir / MODEL_CONFIG.get("model_file", "model.pkl")

        model_info: Dict[str, Any] = {
            "version": version_dir.name,
            "path": str(version_dir),
            "model_file_exists": model_path.exists(),
            "metadata_file_exists": metadata_path.exists(),
        }

        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            model_info["metadata"] = meta

        # Jangan pernah expose file model atau file path absolut
        models.append(model_info)

    return models


@router.get("/{version}", summary="Get model metadata by version")
async def get_model(version: str) -> Dict[str, Any]:
    """Dapatkan metadata model berdasarkan versi."""
    registry_path = Path(MODEL_CONFIG["registry_path"])
    version_path = registry_path / version

    if not version_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Model versi '{version}' tidak ditemukan",
        )

    metadata_file = version_path / MODEL_CONFIG.get("metadata_file", "metadata.json")
    model_file = version_path / MODEL_CONFIG.get("model_file", "model.pkl")

    info: Dict[str, Any] = {
        "version": version,
        "model_file_exists": model_file.exists(),
        "metadata_file_exists": metadata_file.exists(),
    }

    if metadata_file.exists():
        with open(metadata_file, "r", encoding="utf-8") as f:
            info["metadata"] = json.load(f)
    else:
        info["metadata"] = {}

    return info
