from __future__ import annotations

import asyncio
import hmac
import os
import threading
import time
import uuid
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse


PUBLIC_PROBE_PATHS = {"/health", "/health/live", "/health/ready", "/version", "/openapi.json"}


def _positive_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


@dataclass(frozen=True)
class GatewaySettings:
    mode: str
    expected_front_door_id: str
    apim_backend_secret: str
    rate_limit_calls: int
    rate_limit_window_seconds: int
    max_request_bytes: int
    request_timeout_seconds: int

    @classmethod
    def from_environment(cls) -> "GatewaySettings":
        mode = os.getenv("APPROVED_GATEWAY_MODE", "none").strip().lower()
        if mode not in {"none", "frontdoor", "apim"}:
            mode = "none"
        return cls(
            mode=mode,
            expected_front_door_id=os.getenv("EXPECTED_AZURE_FRONT_DOOR_ID", "").strip(),
            apim_backend_secret=os.getenv("APIM_BACKEND_SHARED_SECRET", "").strip(),
            rate_limit_calls=_positive_int("STAGING_RATE_LIMIT_CALLS", 120),
            rate_limit_window_seconds=_positive_int("STAGING_RATE_LIMIT_WINDOW_SECONDS", 60),
            max_request_bytes=_positive_int("STAGING_MAX_REQUEST_BYTES", 1_048_576),
            request_timeout_seconds=_positive_int("STAGING_REQUEST_TIMEOUT_SECONDS", 60),
        )


class FixedWindowRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[int, int]] = {}

    def allow(self, key: str, calls: int, window_seconds: int, now: float | None = None) -> bool:
        current = int(now if now is not None else time.monotonic())
        window = current // window_seconds
        with self._lock:
            stored_window, count = self._windows.get(key, (window, 0))
            if stored_window != window:
                stored_window, count = window, 0
            count += 1
            self._windows[key] = (stored_window, count)
            if len(self._windows) > 10_000:
                self._windows = {
                    stored_key: value
                    for stored_key, value in self._windows.items()
                    if value[0] >= window - 1
                }
            return count <= calls


limiter = FixedWindowRateLimiter()


def _error(status_code: int, code: str, message: str, correlation_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "correlation_id": correlation_id}},
        headers={"X-Correlation-ID": correlation_id},
    )


def _gateway_is_valid(request: Request, settings: GatewaySettings) -> bool:
    if settings.mode == "none":
        return True
    if settings.mode == "frontdoor":
        supplied = request.headers.get("X-Azure-FDID", "").strip()
        marker = request.headers.get("X-Software-Edge", "").strip()
        return bool(
            settings.expected_front_door_id
            and supplied
            and marker == "azure-front-door"
            and hmac.compare_digest(settings.expected_front_door_id, supplied)
        )
    supplied = request.headers.get("X-APIM-Backend-Key", "").strip()
    return bool(
        settings.apim_backend_secret
        and supplied
        and hmac.compare_digest(settings.apim_backend_secret, supplied)
    )


async def gateway_protection_middleware(request: Request, call_next):
    settings = GatewaySettings.from_environment()
    correlation_id = request.headers.get("X-Correlation-ID", "").strip() or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    is_probe = request.url.path in PUBLIC_PROBE_PATHS

    if not is_probe and not _gateway_is_valid(request, settings):
        return _error(403, "approved_gateway_required", "Use the approved staging endpoint.", correlation_id)

    content_length = request.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > settings.max_request_bytes:
                return _error(413, "payload_too_large", "Request body exceeds the staging limit.", correlation_id)
        except ValueError:
            return _error(400, "invalid_content_length", "Content-Length must be an integer.", correlation_id)

    if not is_probe:
        organization_id = request.headers.get("X-Organization-ID", "").strip()
        client_host = request.client.host if request.client else "unknown"
        rate_key = organization_id or client_host
        if not limiter.allow(rate_key, settings.rate_limit_calls, settings.rate_limit_window_seconds):
            return _error(429, "rate_limit_exceeded", "Staging request rate exceeded.", correlation_id)

    try:
        response = await asyncio.wait_for(call_next(request), timeout=settings.request_timeout_seconds)
    except asyncio.TimeoutError:
        return _error(504, "gateway_timeout", "The staging request timed out.", correlation_id)

    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
    if "Server" in response.headers:
        del response.headers["Server"]
    if "X-Powered-By" in response.headers:
        del response.headers["X-Powered-By"]
    return response
