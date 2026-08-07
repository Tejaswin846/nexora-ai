from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

try:
    from config import Settings
except Exception:
    from .config import Settings


SERVICE_STARTED_AT = datetime.now(timezone.utc)


def uptime_seconds() -> float:
    return round((datetime.now(timezone.utc) - SERVICE_STARTED_AT).total_seconds(), 2)


def component(name: str, status: str, **details: Any) -> dict[str, Any]:
    return {"name": name, "status": status, **details}


def safe_error(error: Exception) -> str:
    return error.__class__.__name__


def redis_check(settings: Settings) -> dict[str, Any]:
    if not (settings.upstash_redis_rest_url and settings.upstash_redis_rest_token):
        return component("redis", "unhealthy" if settings.is_production_like else "degraded", configured=False)
    try:
        response = requests.post(
            settings.upstash_redis_rest_url.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.upstash_redis_rest_token}"},
            json=["PING"],
            timeout=1.5,
        )
        response.raise_for_status()
        return component("redis", "healthy", configured=True)
    except Exception as error:
        return component(
            "redis",
            "unhealthy" if settings.is_production_like else "degraded",
            configured=True,
            error=safe_error(error),
        )


def supabase_check(settings: Settings) -> dict[str, Any]:
    configured = bool(settings.supabase_url and (settings.supabase_anon_key or settings.supabase_service_role_key))
    if not configured:
        return component("supabase", "unhealthy" if settings.is_production else "degraded", configured=False)
    if "/rest/v1" in settings.supabase_url.rstrip("/"):
        return component("supabase", "unhealthy", configured=True, error="SUPABASE_URL must not include /rest/v1/.")
    return component("supabase", "healthy", configured=True)


def database_check(settings: Settings) -> dict[str, Any]:
    if settings.database_url:
        return component("database", "healthy", configured=True, mode="production")
    return component("database", "unhealthy" if settings.is_production else "degraded", configured=False, mode="local")


def storage_check(settings: Settings) -> dict[str, Any]:
    path = Path(settings.data_dir)
    return component("storage", "healthy" if path.exists() else "degraded", path=str(path), exists=path.exists())


def qdrant_check() -> dict[str, Any]:
    configured = bool(os.getenv("QDRANT_URL", "").strip())
    return component(
        "qdrant",
        "degraded" if not configured else "healthy",
        configured=configured,
        role="recommendations_only",
    )


def sentry_check() -> dict[str, Any]:
    configured = bool(os.getenv("SENTRY_DSN", "").strip())
    return component(
        "sentry",
        "degraded" if not configured else "healthy",
        configured=configured,
        role="monitoring_only",
    )


def reliability_engine_check(settings: Settings) -> dict[str, Any]:
    unavailable_policy = os.getenv("NEXORA_RELIABILITY_ENGINE_UNAVAILABLE_POLICY", "fail_closed").strip().lower()
    if unavailable_policy not in {"fail_closed", "escalate", "terminate"}:
        return component("reliability_engine", "unhealthy", policy="invalid")
    return component("reliability_engine", "healthy", policy=unavailable_policy, inline_required=True)


def sdk_check() -> dict[str, Any]:
    return component("sdk", "healthy", public_install=True)


def health_report(settings: Settings) -> dict[str, Any]:
    checks = {
        "database": database_check(settings),
        "redis": redis_check(settings),
        "supabase": supabase_check(settings),
        "storage": storage_check(settings),
        "qdrant": qdrant_check(),
        "sentry": sentry_check(),
        "reliability_engine": reliability_engine_check(settings),
        "sdk": sdk_check(),
    }
    statuses = {item["status"] for item in checks.values()}
    overall = "unhealthy" if "unhealthy" in statuses else "degraded" if "degraded" in statuses else "healthy"
    return {
        "status": overall,
        "checks": checks,
        "version": settings.app_version,
        "uptime": uptime_seconds(),
        "environment": settings.normalized_env,
    }
