from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Response

try:
    from config import Settings
    from dependencies import get_runtime_settings
    from health import health_report
except Exception:
    from ..config import Settings
    from ..dependencies import get_runtime_settings
    from ..health import health_report


router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Service health",
    description="Returns production readiness status for database, Redis, Supabase, storage, SDK, version, uptime, and environment.",
)
def health(response: Response, settings: Settings = Depends(get_runtime_settings)) -> dict:
    payload = health_report(settings)
    if payload["status"] == "unhealthy":
        response.status_code = 503
    return payload


@router.get("/health/live", summary="Liveness probe")
def live() -> dict[str, str]:
    return {"status": "alive"}


def _required_runtime_configuration(settings: Settings) -> list[str]:
    if not settings.is_production_like:
        return []

    missing: list[str] = []
    if not settings.database_url:
        missing.append("DATABASE_URL or SUPABASE_DB_URL")
    if not settings.supabase_url:
        missing.append("SUPABASE_URL")
    if not (settings.supabase_service_role_key or settings.supabase_anon_key):
        missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY")
    for name in (
        "AZURE_SERVICE_BUS_NAMESPACE",
        "AZURE_SERVICE_BUS_QUEUE_NAME",
        "AZURE_STORAGE_ACCOUNT_URL",
    ):
        if not os.getenv(name, "").strip():
            missing.append(name)
    return missing


@router.get("/health/ready", summary="Readiness probe")
def ready(response: Response, settings: Settings = Depends(get_runtime_settings)) -> dict:
    missing = _required_runtime_configuration(settings)
    payload = health_report(settings)
    ready_status = not missing and payload["status"] != "unhealthy"
    if not ready_status:
        response.status_code = 503
    return {
        "status": "ready" if ready_status else "not_ready",
        "environment": settings.normalized_env,
        "missing_configuration": missing,
        "application": payload["status"],
    }


@router.get("/version", summary="Build version")
def version(settings: Settings = Depends(get_runtime_settings)) -> dict[str, str]:
    return {
        "version": os.getenv("APP_VERSION", settings.app_version).strip() or settings.app_version,
        "git_commit_sha": os.getenv("GIT_COMMIT_SHA", "unknown").strip() or "unknown",
        "environment": settings.normalized_env,
        "build_timestamp": os.getenv("BUILD_TIMESTAMP", "unknown").strip() or "unknown",
    }
