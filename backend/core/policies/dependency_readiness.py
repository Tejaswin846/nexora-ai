from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class DependencyStatus(str, Enum):
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class DependencyPolicy:
    name: str
    required_for_inline: bool
    fail_closed: bool
    can_degrade: bool
    safe_public_message: str

    def evaluate(self, checker: Callable[[], bool]) -> DependencyStatus:
        try:
            return DependencyStatus.READY if checker() else self._unavailable_status()
        except Exception:
            return self._unavailable_status()

    def _unavailable_status(self) -> DependencyStatus:
        if self.required_for_inline or self.fail_closed:
            return DependencyStatus.UNAVAILABLE
        return DependencyStatus.DEGRADED if self.can_degrade else DependencyStatus.UNAVAILABLE


SUPABASE_POSTGRES_POLICY = DependencyPolicy(
    name="supabase_postgres",
    required_for_inline=True,
    fail_closed=True,
    can_degrade=False,
    safe_public_message="Database dependency is not ready.",
)
REDIS_SECURITY_POLICY = DependencyPolicy(
    name="redis_security_controls",
    required_for_inline=False,
    fail_closed=True,
    can_degrade=False,
    safe_public_message="Security rate limiting is unavailable.",
)
QDRANT_RECOMMENDATION_POLICY = DependencyPolicy(
    name="qdrant_recommendations",
    required_for_inline=False,
    fail_closed=False,
    can_degrade=True,
    safe_public_message="Recommendation similarity features are degraded.",
)
SENTRY_MONITORING_POLICY = DependencyPolicy(
    name="sentry_monitoring",
    required_for_inline=False,
    fail_closed=False,
    can_degrade=True,
    safe_public_message="Error reporting is degraded.",
)
