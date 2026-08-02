"""
Commute service: orchestrator untuk Safe Commute fitur.

Alur:
1. Dapatkan route dari routing service (road network + segments)
2. Ambil titik/segmen route
3. Hitung risk score pada setiap titik route (menggunakan model service)
4. Hitung route-level risk score (aggregasi)
5. Tentukan risk level
6. Pilih rekomendasi

Dependency:
- routing_service.py  → mendapatkan route dari routing provider
- model_service.py    → inference risk score per titik
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from apps.bootstrap.config import ROUTE_SCORING_CONFIG
from apps.schemas.commute import (
    SafeCommuteRequest,
    SafeCommuteResponse,
    RoutePoint,
)
from apps.services.model_service import ModelService
from apps.services.routing_service import RoutingService, RouteResult


class CommuteService:
    """
    Orchestrator untuk Safe Commute.

    Bertanggung jawab atas:
    - Mendapatkan route dari routing service
    - Membagi route menjadi segmen
    - Memprediksi risk score per segmen
    - Mengaggregasi route-level risk score
    - Menentukan risk level
    - Membuat rekomendasi
    """

    def __init__(self) -> None:
        self._model_service = ModelService.get_instance()
        self._routing_service = RoutingService.get_instance()

    def plan_safe_commute(
        self,
        request: SafeCommuteRequest,
    ) -> SafeCommuteResponse:
        """
        Rencanakan safe commute dari start → destination.

        Args:
            request: SafeCommuteRequest dengan start, destination, hour, day

        Returns:
            SafeCommuteResponse dengan route, distance, duration, risk_score, risk_level
        """
        start = (request.start.lat, request.start.lon)
        end = (request.destination.lat, request.destination.lon)
        hour = request.hour
        day = request.day

        # Step 1: Dapatkan route dari routing provider
        route: RouteResult = self._routing_service.get_route(
            start=start,
            end=end,
        )

        if not route.success:
            # Graceful degradation: jika routing gagal, gunakan garis lurus
            route = self._fallback_straight_line_route(
                start=start,
                end=end,
                error=route.error,
            )

        # Step 2: Sample points along route
        sampled_points = self._sample_route_points(
            route.geometry,
            max_points=ROUTE_SCORING_CONFIG.get("sample_points_per_segment", 5),
        )

        # Step 3: Predict risk score per sampled point
        segment_risks: List[RoutePoint] = []
        risk_scores: List[float] = []
        segment_weights: List[float] = []  # panjang segmen (meter) untuk weighting

        for i, (lat, lon) in enumerate(sampled_points):
            risk_score, risk_level, _ = self._model_service.predict(
                lat=lat,
                lon=lon,
                hour=hour,
                day=day,
            )

            segment_risks.append(RoutePoint(
                lat=float(lat),
                lon=float(lon),
                risk_score=round(risk_score, 2),
            ))
            risk_scores.append(risk_score)

            # Weight = panjang segmen (dari point i ke point i+1)
            if i < len(sampled_points) - 1:
                next_lat, next_lon = sampled_points[i + 1]
                weight = self._haversine_distance(lat, lon, next_lat, next_lon)
            else:
                weight = 1.0  # titik terakhir, weight minimal

            segment_weights.append(weight)

        # Step 4: Hitung route-level risk score
        route_risk_score = self._aggregate_risk_scores(
            risk_scores, segment_weights
        )

        # Step 5: Tentukan risk level
        risk_level = self._model_service._score_to_level(route_risk_score)

        # Step 6: Rekomendasi
        recommendation = self._generate_recommendation(
            risk_score=route_risk_score,
            risk_level=risk_level,
            distance_meters=route.distance_meters,
            duration_seconds=route.duration_seconds,
            provider=route.provider,
            routing_error=route.error,
        )

        return SafeCommuteResponse(
            route=route.geometry,
            distance_meters=round(route.distance_meters, 1),
            duration_seconds=round(route.duration_seconds, 1),
            route_risk_score=round(route_risk_score, 2),
            risk_level=risk_level,
            segment_risks=segment_risks,
            recommendation=recommendation,
            routing_provider=route.provider,
        )

    # ------------------------------------------------------------------
    # Route sampling
    # ------------------------------------------------------------------
    @staticmethod
    def _sample_route_points(
        geometry: List[List[float]],
        max_points: int,
    ) -> List[Tuple[float, float]]:
        """
        Sample points evenly along route geometry.
        Geometry format: list of [lon, lat] (GeoJSON format).

        Returns list of (lat, lon) tuples.
        """
        if not geometry or len(geometry) <= max_points:
            # Gunakan semua titik
            return [(lat, lon) for lon, lat in geometry]

        # Sample evenly
        indices = np.linspace(0, len(geometry) - 1, max_points, dtype=int)
        points = []
        for idx in indices:
            lon, lat = geometry[idx]
            points.append((float(lat), float(lon)))
        return points

    # ------------------------------------------------------------------
    # Distance calculation (Haversine)
    # ------------------------------------------------------------------
    @staticmethod
    def _haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Hitung jarak antar dua titik dalam meter menggunakan Haversine formula."""
        R = 6_371_000  # Earth radius in meters
        phi1 = np.radians(lat1)
        phi2 = np.radians(lat2)
        delta_phi = np.radians(lat2 - lat1)
        delta_lambda = np.radians(lon2 - lon1)

        a = (
            np.sin(delta_phi / 2) ** 2
            + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2) ** 2
        )
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        return float(R * c)

    # ------------------------------------------------------------------
    # Risk aggregation
    # ------------------------------------------------------------------
    def _aggregate_risk_scores(
        self,
        scores: List[float],
        weights: List[float],
    ) -> float:
        """Agregasi risk scores berdasarkan metode di config."""
        method = ROUTE_SCORING_CONFIG.get("aggregation_method", "weighted_average")

        if not scores:
            return 0.0

        if method == "max":
            return max(scores)
        elif method == "mean":
            return float(np.mean(scores))
        elif method == "weighted_average":
            total_weight = sum(weights)
            if total_weight == 0:
                return float(np.mean(scores))
            weighted_sum = sum(s * w for s, w in zip(scores, weights))
            return weighted_sum / total_weight
        else:
            return float(np.mean(scores))

    # ------------------------------------------------------------------
    # Fallback: straight-line route (if routing API fails)
    # ------------------------------------------------------------------
    @staticmethod
    def _fallback_straight_line_route(
        start: Tuple[float, float],
        end: Tuple[float, float],
        error: Optional[str] = None,
    ) -> RouteResult:
        """
        Buat route garis lurus sebagai fallback ketika routing API gagal.
        """
        lat1, lon1 = start
        lat2, lon2 = end

        # Jarak garis lurus
        distance = CommuteService._haversine_distance(lat1, lon1, lat2, lon2)
        # Estimasi durasi (asumsi 50 km/h rata-rata)
        duration = distance / (50.0 * 1000.0 / 3600.0) if distance > 0 else 0.0

        # Buat geometry garis lurus (10 titik)
        n = 10
        coords = []
        for i in range(n):
            frac = i / (n - 1)
            lat = lat1 + (lat2 - lat1) * frac
            lon = lon1 + (lon2 - lon1) * frac
            coords.append([lon, lat])

        return RouteResult(
            geometry=coords,
            distance_meters=distance,
            duration_seconds=duration,
            provider="straight_line_fallback",
            raw={"error": error} if error else {},
            success=True,
            error=error,
        )

    # ------------------------------------------------------------------
    # Recommendation
    # ------------------------------------------------------------------
    def _generate_recommendation(
        self,
        risk_score: float,
        risk_level: str,
        distance_meters: float,
        duration_seconds: float,
        provider: str,
        routing_error: Optional[str],
    ) -> str:
        """Buat rekomendasi teks berdasarkan hasil analisis."""
        parts = []

        if routing_error:
            parts.append(
                f"Catatan: routing API mengembalikan error '{routing_error}'. "
                f"Rute dihitung menggunakan garis lurus (fallback)."
            )

        if risk_level == "High":
            parts.append(
                "⚠️ Rute ini memiliki RISIKO TINGGI. "
                "Pertimbangkan untuk mengubah rute, menghindari area ini, "
                "atau menyesuaikan waktu keberangkatan."
            )
        elif risk_level == "Medium":
            parts.append(
                "⚡ Rute ini memiliki RISIKO SEDANG. "
                "Wajib hati-hati, hindari berhenti di area yang tidak ramai, "
                "dan pertimbangkan rute alternatif."
            )
        else:
            parts.append(
                "✅ Rute ini relatif AMAN. "
                "Nikmati perjalanan dengan tetap waspada."
            )

        if distance_meters > 0:
            dist_km = distance_meters / 1000.0
            parts.append(f"Jarak: {dist_km:.1f} km")

        if duration_seconds > 0:
            dur_min = duration_seconds / 60.0
            parts.append(f"Estimasi waktu: {dur_min:.1f} menit")

        parts.append(f"Provider routing: {provider}")

        return " | ".join(parts)

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------
    _instance: Optional["CommuteService"] = None

    @classmethod
    def get_instance(cls) -> "CommuteService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
