"""
Schema request & response untuk endpoint Risk Score.

Bentuk response ini mengikuti PERSIS contoh resmi di task document CP2
(bukan envelope BaseResponseData ala materi Session 3) -- flat JSON:
    {"risk_score": 74, "level": "High", "model_version": "v3", "last_updated": "..."}

Kalau tim FE lebih nyaman dengan envelope {status, message, data} seperti
di materi Session 3 / contoh Taxi Pricing API, tinggal bungkus RiskScoreResponse
ini di dalam envelope itu saat didiskusikan -- struktur di bawah tetap valid
sebagai isi `data`-nya.
"""

from pydantic import BaseModel, Field


class RiskScoreResponse(BaseModel):
    risk_score: float = Field(..., ge=0, le=100, description="Estimasi skor risiko, 0-100")
    level: str = Field(..., description="Kategori risiko: Low, Medium, atau High")
    model_version: str = Field(..., description="Versi model yang menghasilkan prediksi ini")
    last_updated: str = Field(..., description="Timestamp ISO 8601 kapan model ini terakhir dilatih")

    model_config = {
        "json_schema_extra": {
            "example": {
                "risk_score": 74.0,
                "level": "High",
                "model_version": "v1",
                "last_updated": "2026-08-01T04:33:56",
            }
        }
    }


class ErrorResponse(BaseModel):
    detail: str
