import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.controller import RiskModelRegistry
from app.router import router

# --------------------------------------------------------------------------
# Paths & config — semua berbasis Path(__file__) agar tidak bergantung
# pada current working directory saat uvicorn dijalankan.
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
REGISTRY_DIR = BASE_DIR / "model_registry"
MODEL_VERSION = os.environ.get("MODEL_VERSION", "v1")

# Load .env jika tersedia (opsional, hanya untuk development)
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
    MODEL_VERSION = os.environ.get("MODEL_VERSION", "v1")
except ImportError:
    pass  # python-dotenv tidak wajib — env vars tetap bisa di-set secara manual


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load model + metadata SEKALI saat startup, simpan di app.state supaya
    # semua request pakai instance yang sama (bukan re-load tiap request).
    app.state.registry = RiskModelRegistry(REGISTRY_DIR, version=MODEL_VERSION)
    print(f"Model registry '{MODEL_VERSION}' loaded. "
          f"MAE test: {app.state.registry.metadata['metrics']['mae_test']}")
    yield


app = FastAPI(
    title="Women Safety & Smart Protection -- Risk Score API",
    description="Estimasi risk_score (0-100) untuk lokasi & waktu tertentu, "
                 "berbasis pola kejahatan historis (proxy Chicago -> Jabodetabek). "
                 "Estimasi berbasis pola historis, BUKAN prediksi kepastian suatu kejadian.",
    version=MODEL_VERSION,
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/", tags=["Health Check"])
def index():
    return {"status": 200, "message": "OK"}


@app.get("/health", tags=["Health Check"])
def health():
    return {"status": 200, "message": "OK"}
