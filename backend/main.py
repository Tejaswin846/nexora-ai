from __future__ import annotations

import hmac
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

try:
    import runtime
    from config import get_settings
    from database import init_database, validate_database_settings
    from exception_handlers import register_exception_handlers
    from observability import configure_logging, request_context_middleware
    import posthog_client
    from routes.auth_routes import router as auth_router
    from routes.benchmark_routes import router as benchmark_router
    from routes.billing_routes import router as billing_router
    from routes.connector_routes import router as connector_router
    from routes.dashboard_routes import router as dashboard_router
    from routes.health_routes import router as health_router
    from routes.job_routes import router as job_router
    from routes.onboarding_routes import router as onboarding_router
    from routes.project_routes import router as project_router
    from routes.reliability_routes import router as reliability_router
    from routes.sdk_routes import router as sdk_router
    from routes.settings_routes import router as settings_router
    from routes.static_routes import router as static_router
except Exception:
    from . import runtime
    from .config import get_settings
    from .database import init_database, validate_database_settings
    from .exception_handlers import register_exception_handlers
    from .observability import configure_logging, request_context_middleware
    from . import posthog_client
    from .routes.auth_routes import router as auth_router
    from .routes.benchmark_routes import router as benchmark_router
    from .routes.billing_routes import router as billing_router
    from .routes.connector_routes import router as connector_router
    from .routes.dashboard_routes import router as dashboard_router
    from .routes.health_routes import router as health_router
    from .routes.job_routes import router as job_router
    from .routes.onboarding_routes import router as onboarding_router
    from .routes.project_routes import router as project_router
    from .routes.reliability_routes import router as reliability_router
    from .routes.sdk_routes import router as sdk_router
    from .routes.settings_routes import router as settings_router
    from .routes.static_routes import router as static_router


settings = get_settings()
configure_logging(settings)
SupabaseAuthError = runtime.SupabaseAuthError
supabase_auth_client = runtime.supabase_auth_client


def _export_runtime_symbols() -> None:
    for name in dir(runtime):
        if not name.startswith("_"):
            globals().setdefault(name, getattr(runtime, name))


_export_runtime_symbols()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.validate_startup()
    validate_database_settings(settings)
    init_database(settings)
    runtime.startup_native_nexora_core()
    posthog_client.init_posthog(
        project_api_key=settings.posthog_api_key,
        host=settings.posthog_host,
        enabled=settings.posthog_enabled,
        ai_observability_enabled=settings.posthog_ai_observability_enabled,
        capture_prompts=settings.posthog_capture_prompts,
        capture_responses=settings.posthog_capture_responses,
        privacy_mode=settings.posthog_privacy_mode,
    )
    try:
        yield
    finally:
        runtime.NEXORA_CORE_STOP.set()
        thread = getattr(runtime, "NEXORA_CORE_THREAD", None)
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        posthog_client.shutdown_posthog()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=bool(settings.cors_allowed_origins),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID", "X-Organization-ID", "X-Project-ID"],
)


@app.middleware("http")
async def capture_api_requests(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as error:
        latency_ms = int((time.perf_counter() - started) * 1000)
        posthog_client.capture_request_error(request, error, latency_ms)
        raise

    latency_ms = int((time.perf_counter() - started) * 1000)
    posthog_client.capture_request_completed(request, response, latency_ms)
    return response


@app.middleware("http")
async def sync_runtime_test_overrides(request: Request, call_next):
    runtime.SupabaseAuthError = globals().get("SupabaseAuthError", runtime.SupabaseAuthError)
    runtime.supabase_auth_client = globals().get("supabase_auth_client", runtime.supabase_auth_client)
    return await call_next(request)


@app.middleware("http")
async def enforce_auth_rate_limit(request: Request, call_next):
    if request.url.path.startswith("/auth/"):
        verdict = runtime.check_rate_limit(request)
        if not verdict.get("allowed"):
            return JSONResponse(
                status_code=int(verdict.get("status_code") or 503),
                content={
                    "ok": False,
                    "detail": verdict.get("detail") or runtime.AUTH_PROTECTION_UNAVAILABLE_MESSAGE,
                    "rate_limit_storage": verdict.get("storage", "unknown"),
                },
            )
    return await call_next(request)


@app.middleware("http")
async def add_private_network_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


app.middleware("http")(request_context_middleware)


@app.middleware("http")
async def require_approved_backend_path(request: Request, call_next):
    enabled = os.getenv("REQUIRE_APIM_BACKEND_HEADER", "false").strip().lower() in {"1", "true", "yes", "on"}
    public_probe_paths = {"/health", "/health/live", "/health/ready", "/version", "/openapi.json"}
    if enabled and request.url.path not in public_probe_paths:
        expected = os.getenv("APIM_BACKEND_SHARED_SECRET", "").strip()
        supplied = request.headers.get("X-APIM-Backend-Key", "").strip()
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "approved_gateway_required", "message": "Use the approved API endpoint."}},
            )
    return await call_next(request)

for router in (
    health_router,
    job_router,
    static_router,
    auth_router,
    dashboard_router,
    project_router,
    connector_router,
    reliability_router,
    sdk_router,
    billing_router,
    benchmark_router,
    settings_router,
    onboarding_router,
):
    app.include_router(router)

register_exception_handlers(app, legacy_handler=runtime.runtime_exception_handler)


if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("NEXORA_RELOAD", "false").strip().lower() in {"1", "true", "yes"},
    )
