"""
Routing service: abstraksi untuk mendapatkan road network/route dari
external routing provider.

Provider yang didukung:
- OSRM (Open Source Routing Machine) — DEFAULT, tidak perlu API key
- OpenRouteService — perlu API key
- GraphHopper — perlu API key

API key diambil dari environment variable ROUTING_API_KEY.
Provider dapat diganti dengan mudah melalui config.yaml → routing.provider.

Interface publik:
  get_route(start, end, profile) -> RouteResult
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx

from apps.bootstrap.config import ROUTING_CONFIG, get_env


@dataclass
class RouteWaypoint:
    """A single waypoint on a route."""
    lat: float
    lon: float


@dataclass
class RouteResult:
    """Hasil route dari routing provider."""
    # Geometry as list of [lon, lat] pairs (GeoJSON LineString format)
    geometry: List[List[float]] = field(default_factory=list)
    # Total distance in meters
    distance_meters: float = 0.0
    # Total duration in seconds
    duration_seconds: float = 0.0
    # Provider name (osrm, openrouteservice, graphhopper)
    provider: str = "unknown"
    # Raw response (untuk debugging, tanpa API key)
    raw: Optional[Dict[str, Any]] = None
    # Flag apakah request berhasil
    success: bool = True
    # Error message jika gagal
    error: Optional[str] = None


class RoutingProvider:
    """Base class untuk routing provider."""

    provider_name: str = "base"

    def get_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        profile: str = "car",
        timeout: int = 10,
    ) -> RouteResult:
        raise NotImplementedError


class OSRMProvider(RoutingProvider):
    """
    OSRM public API (https://router.project-osrm.org).
    Tidak memerlukan API key.
    """

    provider_name = "osrm"

    def __init__(self, base_url: str = "https://router.project-osrm.org"):
        self.base_url = base_url.rstrip("/")

    def get_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        profile: str = "car",
        timeout: int = 10,
    ) -> RouteResult:
        # OSRM format: lon,lat (bukan lat,lon)
        lon1, lat1 = start[1], start[0]
        lon2, lat2 = end[1], end[0]

        # OSRM profile mapping: car -> driving, walking -> walking, cycling -> cycling
        osrm_profile = {
            "car": "driving",
            "driving": "driving",
            "walking": "walking",
            "cycling": "cycling",
            "bike": "cycling",
        }.get(profile, "driving")

        url = f"{self.base_url}/route/v1/{osrm_profile}/{lon1},{lat1};{lon2},{lat2}"
        params = {
            "overview": "full",
            "geometries": "geojson",
            "alternatives": "false",
            "steps": "false",
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            if data.get("code") != "Ok":
                return RouteResult(
                    provider=self.provider_name,
                    success=False,
                    error=f"OSRM error: {data.get('message', 'Unknown error')}",
                )

            route = data["routes"][0]
            # GeoJSON geometry: list of [lon, lat]
            coords = route["geometry"]["coordinates"]

            return RouteResult(
                geometry=coords,
                distance_meters=float(route.get("distance", 0)),
                duration_seconds=float(route.get("duration", 0)),
                provider=self.provider_name,
                raw={"code": data["code"], "weight_name": route.get("weight_name")},
                success=True,
            )

        except httpx.HTTPError as e:
            return RouteResult(
                provider=self.provider_name,
                success=False,
                error=f"HTTP error: {type(e).__name__}: {e}",
            )
        except Exception as e:
            return RouteResult(
                provider=self.provider_name,
                success=False,
                error=f"{type(e).__name__}: {e}",
            )


class OpenRouteServiceProvider(RoutingProvider):
    """
    OpenRouteService API (https://api.openrouteservice.org).
    Membutuhkan API key via environment variable ROUTING_API_KEY.
    """

    provider_name = "openrouteservice"

    def __init__(self, base_url: str = "https://api.openrouteservice.org"):
        self.base_url = base_url.rstrip("/")
        self.api_key = get_env("ROUTING_API_KEY", "")

    def get_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        profile: str = "car",
        timeout: int = 10,
    ) -> RouteResult:
        if not self.api_key:
            return RouteResult(
                provider=self.provider_name,
                success=False,
                error="ROUTING_API_KEY environment variable tidak di-set",
            )

        # ORS API: lat,lon format
        lat1, lon1 = start[0], start[1]
        lat2, lon2 = end[0], end[1]

        ors_profile = {
            "car": "driving-car",
            "driving": "driving-car",
            "walking": "foot-walking",
            "cycling": "cycling-regular",
        }.get(profile, "driving-car")

        url = f"{self.base_url}/v2/directions/{ors_profile}"
        params = {"api_key": self.api_key}
        body = {
            "coordinates": [[lon1, lat1], [lon2, lat2]],
            "format": "geojson",
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, params=params, json=body)
                resp.raise_for_status()
                data = resp.json()

            # GeoJSON LineString
            coords = data["geometry"]["coordinates"]

            # Get distance & duration from segments
            distance = 0.0
            duration = 0.0
            for seg in data.get("features", [data]).get("properties", {}).get("segments", []):
                distance += seg.get("distance", 0)
                duration += seg.get("duration", 0)

            # Fallback: parse from properties
            if distance == 0 and "properties" in data and "summary" in data["properties"]:
                summary = data["properties"]["summary"]
                distance = summary.get("distance", 0)
                duration = summary.get("duration", 0)

            return RouteResult(
                geometry=coords,
                distance_meters=float(distance),
                duration_seconds=float(duration),
                provider=self.provider_name,
                raw={"status": "ok"},
                success=True,
            )

        except httpx.HTTPError as e:
            return RouteResult(
                provider=self.provider_name,
                success=False,
                error=f"HTTP error: {type(e).__name__}: {e}",
            )
        except Exception as e:
            return RouteResult(
                provider=self.provider_name,
                success=False,
                error=f"{type(e).__name__}: {e}",
            )


class GraphHopperProvider(RoutingProvider):
    """
    GraphHopper API (https://graphhopper.com/api/1).
    Membutuhkan API key via environment variable ROUTING_API_KEY.
    """

    provider_name = "graphhopper"

    def __init__(self, base_url: str = "https://graphhopper.com/api/1"):
        self.base_url = base_url.rstrip("/")
        self.api_key = get_env("ROUTING_API_KEY", "")

    def get_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        profile: str = "car",
        timeout: int = 10,
    ) -> RouteResult:
        if not self.api_key:
            return RouteResult(
                provider=self.provider_name,
                success=False,
                error="ROUTING_API_KEY environment variable tidak di-set",
            )

        lat1, lon1 = start[0], start[1]
        lat2, lon2 = end[0], end[1]

        gh_profile = {
            "car": "car",
            "driving": "car",
            "walking": "foot",
            "cycling": "bike",
        }.get(profile, "car")

        url = f"{self.base_url}/route"
        params = {
            "point": [f"{lat1},{lon1}", f"{lat2},{lon2}"],
            "vehicle": gh_profile,
            "locale": "en",
            "points_enabled": "false",
            "type": "json",
            "key": self.api_key,
            "instructions": "false",
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            if not data.get("paths"):
                return RouteResult(
                    provider=self.provider_name,
                    success=False,
                    error=f"GraphHopper error: {data.get('info', {}).get('errors', ['Unknown'])}",
                )

            path = data["paths"][0]
            # GraphHopper points: list of [lat, lon] → convert to [lon, lat]
            coords = [[p[1], p[0]] for p in path["points"]["coordinates"]]

            return RouteResult(
                geometry=coords,
                distance_meters=float(path.get("distance", 0)),
                duration_seconds=float(path.get("time", 0)) / 1000.0,  # ms → s
                provider=self.provider_name,
                raw={"points_count": len(coords)},
                success=True,
            )

        except httpx.HTTPError as e:
            return RouteResult(
                provider=self.provider_name,
                success=False,
                error=f"HTTP error: {type(e).__name__}: {e}",
            )
        except Exception as e:
            return RouteResult(
                provider=self.provider_name,
                success=False,
                error=f"{type(e).__name__}: {e}",
            )


# -----------------------------------------------------------------------
# Provider factory
# -----------------------------------------------------------------------
_PROVIDER_MAP: Dict[str, type[RoutingProvider]] = {
    "osrm": OSRMProvider,
    "openrouteservice": OpenRouteServiceProvider,
    "graphhopper": GraphHopperProvider,
}


class RoutingService:
    """
    Service untuk routing. Abstraksi provider sehingga provider dapat
    diganti dengan mudah melalui config.yaml.

    Provider di-load berdasarkan config 'routing.provider'.
    API key (jika diperlukan) diambil dari environment variable.
    """

    def __init__(self) -> None:
        provider_name = ROUTING_CONFIG.get("provider", "osrm").lower()
        provider_cls = _PROVIDER_MAP.get(provider_name)

        if provider_cls is None:
            raise ValueError(
                f"Routing provider tidak dikenal: '{provider_name}'. "
                f"Provider yang didukung: {list(_PROVIDER_MAP.keys())}"
            )

        # Build provider-specific config
        provider_config = ROUTING_CONFIG.get(provider_name, {})
        base_url = provider_config.get("base_url", "")
        timeout = provider_config.get("timeout_seconds", 10)

        if provider_name == "osrm":
            self._provider: RoutingProvider = OSRMProvider(base_url=base_url)
        elif provider_name == "openrouteservice":
            self._provider = OpenRouteServiceProvider(base_url=base_url)
        elif provider_name == "graphhopper":
            self._provider = GraphHopperProvider(base_url=base_url)

        self._timeout = timeout
        self._profile = provider_config.get("profile", "car")

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    def get_route(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        profile: Optional[str] = None,
    ) -> RouteResult:
        """
        Dapatkan route dari start ke end.

        Args:
            start: (lat, lon)
            end: (lat, lon)
            profile: driving/walking/cycling (default dari config)

        Returns:
            RouteResult — berisi geometry, distance, duration, provider, status
        """
        return self._provider.get_route(
            start=start,
            end=end,
            profile=profile or self._profile,
            timeout=self._timeout,
        )

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------
    _instance: Optional["RoutingService"] = None

    @classmethod
    def get_instance(cls) -> "RoutingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
