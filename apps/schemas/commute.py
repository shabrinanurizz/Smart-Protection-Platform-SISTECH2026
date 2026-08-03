"""
Pydantic schemas untuk Safe Commute API.

Request:
  POST /safe-commute
  {
    "start": {"lat": -6.2, "lon": 106.8},
    "destination": {"lat": -6.21, "lon": 106.82},
    "hour": 22,
    "day": "Saturday"
  }

Response:
  {
    "route": [...],
    "distance_meters": 1234.5,
    "duration_seconds": 300.0,
    "route_risk_score": 62.5,
    "risk_level": "Medium",
    "recommendation": "..."
  }
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


MIN_LAT = -6.55
MAX_LAT = -6.10
MIN_LON = 106.55
MAX_LON = 107.55

"""lat_new_min = -6.55   
lat_new_max = -6.10   
lon_new_min = 106.55  
lon_new_max = 107.05 
"""


class Location(BaseModel):
    """A geographic coordinate (latitude, longitude)."""

    lat: float = Field(..., description="Latitude (decimal degrees)")
    lon: float = Field(..., description="Longitude (decimal degrees)")

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


class SafeCommuteRequest(BaseModel):
    """Request body untuk endpoint POST /safe-commute."""

    start: Location = Field(..., description="Titik awal perjalanan")
    destination: Location = Field(..., description="Titik tujuan perjalanan")
    hour: int = Field(..., ge=0, le=23, description="Waktu keberangkatan (0-23)")
    day: str = Field(..., description="Hari perjalanan (e.g. 'Saturday')")

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


class RoutePoint(BaseModel):
    """A single point on a route with its risk prediction."""

    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Risk score at this point")


class SafeCommuteResponse(BaseModel):
    """Response body untuk endpoint POST /safe-commute."""

    route: List[List[float]] = Field(
        ..., description="Route geometry as list of [lon, lat] pairs"
    )
    distance_meters: float = Field(..., description="Total route distance in meters")
    duration_seconds: float = Field(..., description="Estimated travel time in seconds")
    route_risk_score: float = Field(
        ..., ge=0.0, le=100.0, description="Aggregated risk score for the entire route"
    )
    risk_level: str = Field(..., description="Risk level: Low, Medium, atau High")
    segment_risks: List[RoutePoint] = Field(
        default_factory=list,
        description="Risk scores at sampled points along the route"
    )
    recommendation: str = Field(..., description="Human-readable recommendation text")
    routing_provider: str = Field(..., description="Routing API provider yang digunakan")
