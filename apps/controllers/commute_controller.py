"""
Commute controller: menangani HTTP request untuk Safe Commute.

Controller bertugas sebagai jembatan antara router (HTTP) dan service (business logic).
Controller hanya melakukan:
- Validasi input (via Pydantic schema)
- Delegasi ke commute service
- Mapping hasil ke response schema
- Logging
"""

from __future__ import annotations

from apps.schemas.commute import SafeCommuteRequest, SafeCommuteResponse
from apps.services.commute_service import CommuteService


class CommuteController:
    """Controller untuk endpoint POST /safe-commute."""

    def __init__(self) -> None:
        self._commute_service = CommuteService.get_instance()

    def plan_commute(
        self,
        request: SafeCommuteRequest,
    ) -> SafeCommuteResponse:
        """
        Rencanakan safe commute dari start → destination.

        Args:
            request: SafeCommuteRequest (start, destination, hour, day)

        Returns:
            SafeCommuteResponse (route, distance, duration, risk_score, risk_level, ...)
        """
        return self._commute_service.plan_safe_commute(request)
