from __future__ import annotations

import logging
import sqlite3
from typing import Any, Awaitable, Callable, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from requests import RequestException

try:
    from observability import current_request_id
    import posthog_client
    from supabase_client import SupabaseAuthError
except Exception:
    from .observability import current_request_id
    from . import posthog_client
    from .supabase_client import SupabaseAuthError


LegacyHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def request_id_for(request: Request) -> str:
    return getattr(request.state, "request_id", "") or current_request_id()


def error_payload(code: str, message: str, request_id: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        },
    }


def error_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_payload(code, message, request_id_for(request)),
        headers={"X-Request-ID": request_id_for(request)},
    )


def register_exception_handlers(app: FastAPI, legacy_handler: Optional[LegacyHandler] = None) -> None:
    logger = logging.getLogger("nexora.errors")

    def capture_handled_exception(request: Request, exc: Exception, code: str, status_code: int) -> None:
        distinct_id = (
            request.headers.get("x-user-id")
            or request.headers.get("x-posthog-distinct-id")
            or request.headers.get("x-session-id")
            or "anonymous"
        )
        posthog_client.capture_exception(
            exc,
            distinct_id=distinct_id,
            properties={
                "code": code,
                "status_code": status_code,
                "path": request.url.path,
                "method": request.method,
                "request_id": request_id_for(request),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        message = str(exc.detail)
        if exc.status_code >= 400:
            capture_handled_exception(request, exc, "http_error", exc.status_code)
        return error_response(request, exc.status_code, "http_error", message)

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        capture_handled_exception(request, exc, "validation_error", 422)
        return error_response(request, 422, "validation_error", str(exc))

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        capture_handled_exception(request, exc, "validation_error", 422)
        return error_response(request, 422, "validation_error", str(exc))

    @app.exception_handler(sqlite3.DatabaseError)
    async def database_handler(request: Request, exc: sqlite3.DatabaseError) -> JSONResponse:
        logger.exception("database_error", extra={"request_id": request_id_for(request), "route": request.url.path})
        capture_handled_exception(request, exc, "database_error", 503)
        return error_response(request, 503, "database_error", "Database temporarily unavailable.")

    @app.exception_handler(RequestException)
    async def request_exception_handler(request: Request, exc: RequestException) -> JSONResponse:
        logger.exception("upstream_error", extra={"request_id": request_id_for(request), "route": request.url.path})
        capture_handled_exception(request, exc, "upstream_error", 503)
        return error_response(request, 503, "upstream_error", "Upstream service temporarily unavailable.")

    @app.exception_handler(SupabaseAuthError)
    async def supabase_handler(request: Request, exc: SupabaseAuthError) -> JSONResponse:
        capture_handled_exception(request, exc, "supabase_error", exc.status_code)
        return error_response(request, exc.status_code, "supabase_error", exc.message)

    @app.exception_handler(Exception)
    async def unexpected_handler(request: Request, exc: Exception) -> JSONResponse:
        if legacy_handler and request.url.path.startswith("/chat"):
            return await legacy_handler(request, exc)
        logger.exception("unexpected_error", extra={"request_id": request_id_for(request), "route": request.url.path})
        capture_handled_exception(request, exc, "internal_error", 500)
        return error_response(request, 500, "internal_error", "Unexpected server error.")
