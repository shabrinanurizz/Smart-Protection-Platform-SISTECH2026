from fastapi import APIRouter, HTTPException, Query, Request

from app.controller import InvalidDatetimeError, OutOfBoundsError
from app.schemas import RiskScoreResponse

router = APIRouter()


@router.get("/risk-score", response_model=RiskScoreResponse, tags=["Prediction"])
def get_risk_score(
    request: Request,
    lat: float = Query(..., description="Latitude, dalam bounding box Jabodetabek proxy"),
    lon: float = Query(..., description="Longitude, dalam bounding box Jabodetabek proxy"),
    datetime: str = Query(..., description="ISO 8601, contoh: 2026-08-02T14:00:00"),
):
    registry = request.app.state.registry
    try:
        result = registry.predict(lat=lat, lon=lon, dt_str=datetime)
    except OutOfBoundsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except InvalidDatetimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result
