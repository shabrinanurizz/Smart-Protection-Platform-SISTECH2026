"""
Pydantic schemas untuk Risk Prediction API.

Request:
  POST /predict-risk
  { "lat": -6.2, "lon": 106.8, "hour": 22, "day": "Saturday" }

Response:
  { "risk_score": 0.72, "risk_level": "High" }
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


# -----------------------------------------------------------------------
# Validasi geografi
# -----------------------------------------------------------------------
MIN_LAT = -6.55
MAX_LAT = -6.10
MIN_LON = -106.55
MAX_LON = 107.05

"""lat_new_min = -6.55   
lat_new_max = -6.10   
lon_new_min = 106.55  
lon_new_max = 107.05 
"""

class PredictRiskRequest(BaseModel):
    """Request body untuk endpoint POST /predict-risk."""

    lat: float = Field(..., description="Latitude (decimal degrees, -90 to 90)")
    lon: float = Field(..., description="Longitude (decimal degrees, -180 to 180)")
    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    day: str = Field(..., description="Day of week name (e.g. 'Saturday')")

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if not MIN_LAT <= v <= MAX_LAT:
            raise ValueError(f"Latitude harus antara {MIN_LAT} dan {MAX_LAT}")
        return v

    @field_validator("lon")
    @classmethod
    def validate_lon(cls, v: float) -> float:
        if not MIN_LON <= v <= MAX_LON:
            raise ValueError(f"Longitude harus antara {MIN_LON} dan {MAX_LON}")
        return v

    @field_validator("day")
    @classmethod
    def validate_day(cls, v: str) -> str:
        valid_days = {
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday",
        }
        normalized = v.strip().lower()
        if normalized not in valid_days:
            raise ValueError(
                f"Day harus salah satu dari: {', '.join(sorted(valid_days))}"
            )
        return normalized


class PredictRiskResponse(BaseModel):
    """Response body untuk endpoint POST /predict-risk."""

    risk_score: float = Field(
        ..., ge=0.0, le=100.0,
        description="Predicted risk score (0.0 - 100.0)"
    )
    risk_level: str = Field(
        ..., description="Risk level: Low, Medium, atau High"
    )
