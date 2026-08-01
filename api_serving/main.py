from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.controller import RiskModelRegistry
from app.router import router

REGISTRY_DIR = "model_registry"
MODEL_VERSION = "v1"


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
