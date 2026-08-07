from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

try:
    import ai_observability_store
except Exception:
    from .. import ai_observability_store


router = APIRouter(tags=["dashboard"])


class AlertSettingsRequest(BaseModel):
    enabled: bool = True
    latency_ms_threshold: int = Field(5000, ge=0)
    error_rate_threshold: float = Field(0.1, ge=0, le=1)
    token_usage_threshold: int = Field(8000, ge=0)
    notify_email: str = ""
    webhook_url: str = ""


def bounded_limit(limit: Optional[int], default: int = 100) -> int:
    return max(1, min(int(limit or default), 1000))


@router.get("/api/observability")
def observability_dashboard_entry() -> dict[str, Any]:
    return {
        "ok": True,
        "dashboard": "/observability",
        "api": {
            "overview": "/api/observability/overview",
            "requests": "/api/observability/requests",
            "traces": "/api/observability/traces",
            "sessions": "/api/observability/sessions",
            "alerts": "/api/observability/alerts",
        },
    }


@router.get("/api/observability/overview")
def observability_overview() -> dict[str, Any]:
    return ai_observability_store.overview()


@router.get("/api/observability/requests")
def observability_requests(limit: Optional[int] = 100) -> dict[str, Any]:
    return {"ok": True, "requests": ai_observability_store.list_events(bounded_limit(limit))}


@router.get("/api/observability/traces")
def observability_traces(limit: Optional[int] = 50) -> dict[str, Any]:
    return {"ok": True, "traces": ai_observability_store.traces(bounded_limit(limit, 50))}


@router.get("/api/observability/sessions")
def observability_sessions(limit: Optional[int] = 50) -> dict[str, Any]:
    return {"ok": True, "sessions": ai_observability_store.sessions(bounded_limit(limit, 50))}


@router.get("/api/observability/alerts")
def observability_alerts() -> dict[str, Any]:
    return {
        "ok": True,
        "settings": ai_observability_store.get_alert_settings(),
        "active_alerts": ai_observability_store.active_alerts(),
    }


@router.post("/api/observability/alerts")
def save_observability_alerts(req: AlertSettingsRequest) -> dict[str, Any]:
    return {
        "ok": True,
        "settings": ai_observability_store.update_alert_settings(req.model_dump()),
        "active_alerts": ai_observability_store.active_alerts(),
    }


@router.post("/api/observability/demo")
def create_demo_observability_event() -> dict[str, Any]:
    event = ai_observability_store.seed_demo_event()
    return {"ok": True, "event": event, "overview": ai_observability_store.overview()}
