"""
Smart Protection Platform — FastAPI Application Entry Point.

Menyiapkan:
- FastAPI app
- Middleware (tracer: request ID, timing, logging)
- Router: /health, /predict-risk, /safe-commute, /registry, /metrics
- Startup event: load model + encoding maps (singleton)
- Exception handlers

Cara jalankan:
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import sys
from pathlib import Path

# Pastikan project root ada di sys.path (untuk import module absolut)
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.middleware.tracer import TracerMiddleware
from apps.routers import commute, health, monitoring, prediction, registry
from apps.services.model_service import ModelService

# -----------------------------------------------------------------------
# App metadata
# -----------------------------------------------------------------------
app = FastAPI(
    title="Smart Protection Platform",
    description=(
        "API untuk prediksi risiko kejahatan/safety berdasarkan lokasi dan waktu, "
        "serta perencanaan rute aman (Safe Commute)."
    ),
    version="1.0.0",
    contact={
        "name": "Smart Protection Platform Team",
    },
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# -----------------------------------------------------------------------
# Middleware
# -----------------------------------------------------------------------
app.add_middleware(TracerMiddleware)

# CORS (untuk development; production bisa lebih ketat)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------
# Startup — load model & encoding maps (singleton, di-load sekali)
# -----------------------------------------------------------------------
@app.on_event("startup")
async def startup_event() -> None:
    """Load model sekali saat aplikasi mulai."""
    # ModelService singleton akan load otomatis pada get_instance()
    ms = ModelService.get_instance()
    if not ms._initialized:
        raise RuntimeError("Gagal memuat model saat startup")


# -----------------------------------------------------------------------
# Include routers
# -----------------------------------------------------------------------
app.include_router(health.router)       # GET  /health
app.include_router(prediction.router)  # POST /predict-risk/
app.include_router(commute.router)     # POST /safe-commute/
app.include_router(registry.router)    # GET  /registry
app.include_router(monitoring.router)  # GET  /metrics


# -----------------------------------------------------------------------
# Root endpoint
# -----------------------------------------------------------------------
@app.get("/", tags=["Root"], include_in_schema=False)
async def root() -> dict:
    """Root endpoint — redirect ke docs."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
