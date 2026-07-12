from __future__ import annotations

import contextvars
import json
import logging
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Request

try:
    from config import Settings
except Exception:
    from .config import Settings


request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
request_log_sample_rate = 1.0


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "user_id", "project_id", "route", "status", "latency_ms", "error"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(settings: Settings) -> None:
    global request_log_sample_rate
    request_log_sample_rate = min(1.0, max(0.0, settings.request_log_sample_rate))
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    if settings.is_production_like:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root.handlers = [handler]


def current_request_id() -> str:
    return request_id_var.get() or ""


async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    token = request_id_var.set(request_id)
    started_at = time.perf_counter()
    logger = logging.getLogger("nexora.request")
    status = 500
    response = None
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as error:
        logger.exception(
            "request_failed",
            extra={
                "request_id": request_id,
                "route": request.url.path,
                "status": status,
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
                "error": str(error),
            },
        )
        raise
    finally:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        user_id = getattr(request.state, "user_id", None)
        project_id = getattr(request.state, "project_id", None)
        if status >= 500 or random.random() < request_log_sample_rate:
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "project_id": project_id,
                    "route": request.url.path,
                    "status": status,
                    "latency_ms": latency_ms,
                },
            )
        request_id_var.reset(token)
