from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

try:
    import ai_observability_store
    from dependencies import get_current_user
except Exception:
    from .. import ai_observability_store
    from ..dependencies import get_current_user


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


def current_user_id(current_user: dict[str, Any]) -> str:
    return str(current_user.get("id") or "")


@router.get("/api/observability")
def observability_dashboard_entry(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "ok": True,
        "user_id": current_user_id(current_user),
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
def observability_overview(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    return ai_observability_store.overview(user_id=current_user_id(current_user))


@router.get("/api/observability/requests")
def observability_requests(
    limit: Optional[int] = 100,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "ok": True,
        "requests": ai_observability_store.list_events(
            bounded_limit(limit),
            user_id=current_user_id(current_user),
        ),
    }


@router.get("/api/observability/traces")
def observability_traces(
    limit: Optional[int] = 50,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "ok": True,
        "traces": ai_observability_store.traces(
            bounded_limit(limit, 50),
            user_id=current_user_id(current_user),
        ),
    }


@router.get("/api/observability/sessions")
def observability_sessions(
    limit: Optional[int] = 50,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return {
        "ok": True,
        "sessions": ai_observability_store.sessions(
            bounded_limit(limit, 50),
            user_id=current_user_id(current_user),
        ),
    }


@router.get("/api/observability/alerts")
def observability_alerts(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    user_id = current_user_id(current_user)
    return {
        "ok": True,
        "settings": ai_observability_store.get_alert_settings(user_id=user_id),
        "active_alerts": ai_observability_store.active_alerts(user_id=user_id),
    }


@router.post("/api/observability/alerts")
def save_observability_alerts(
    req: AlertSettingsRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    user_id = current_user_id(current_user)
    return {
        "ok": True,
        "settings": ai_observability_store.update_alert_settings(req.model_dump(), user_id=user_id),
        "active_alerts": ai_observability_store.active_alerts(user_id=user_id),
    }


@router.post("/api/observability/demo")
def create_demo_observability_event(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    user_id = current_user_id(current_user)
    event = ai_observability_store.seed_demo_event(user_id=user_id)
    return {
        "ok": True,
        "event": event,
        "overview": ai_observability_store.overview(user_id=user_id),
    }
