from __future__ import annotations

import logging
import re
from typing import Any, Mapping, Optional

import posthog as _posthog

try:
    import ai_observability_store
except Exception:
    from . import ai_observability_store


LOGGER = logging.getLogger("nexora.posthog")

_client: _posthog.Posthog | None = None
_enabled = False
_ai_observability_enabled = True
_capture_prompts = False
_capture_responses = False
_privacy_mode = True

SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|secret|api[_-]?key|authorization|cookie|refresh[_-]?token|access[_-]?token|bearer|jwt)",
    re.IGNORECASE,
)


def init_posthog(
    project_api_key: str = "",
    host: str = "https://us.i.posthog.com",
    *,
    enabled: bool = True,
    ai_observability_enabled: bool = True,
    capture_prompts: bool = False,
    capture_responses: bool = False,
    privacy_mode: bool = True,
) -> None:
    global _client, _enabled, _ai_observability_enabled, _capture_prompts, _capture_responses, _privacy_mode

    _enabled = bool(enabled and project_api_key)
    _ai_observability_enabled = bool(ai_observability_enabled)
    _capture_prompts = bool(capture_prompts)
    _capture_responses = bool(capture_responses)
    _privacy_mode = bool(privacy_mode)

    if not _enabled:
        _client = None
        return

    try:
        _client = _posthog.Posthog(
            project_api_key=project_api_key,
            host=host,
            debug=False,
            privacy_mode=_privacy_mode,
            enable_exception_autocapture=False,
        )
    except Exception:
        LOGGER.exception("posthog_initialization_failed")
        _client = None
        _enabled = False


def shutdown_posthog() -> None:
    global _client
    if _client is None:
        return
    try:
        _client.shutdown()
    except Exception:
        LOGGER.exception("posthog_shutdown_failed")
    finally:
        _client = None


def get_posthog() -> _posthog.Posthog | None:
    return _client


def is_enabled() -> bool:
    return bool(_enabled and _client is not None)


def _clean_distinct_id(distinct_id: Optional[str]) -> str:
    value = str(distinct_id or "").strip()
    return value[:200] if value else "anonymous"


def _safe_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:2000]


def _sanitize_properties(properties: Mapping[str, Any] | None) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in dict(properties or {}).items():
        clean_key = str(key)
        if SENSITIVE_KEY_PATTERN.search(clean_key):
            safe[clean_key] = "[redacted]"
        elif isinstance(value, Mapping):
            safe[clean_key] = _sanitize_properties(value)
        elif isinstance(value, list):
            safe[clean_key] = [
                _sanitize_properties(item) if isinstance(item, Mapping) else _safe_scalar(item)
                for item in value[:25]
            ]
        else:
            safe[clean_key] = _safe_scalar(value)
    return safe


def capture(distinct_id: str = "anonymous", event: str = "", properties: dict[str, Any] | None = None) -> None:
    if not is_enabled() or not event:
        return
    try:
        _client.capture(  # type: ignore[union-attr]
            event=event,
            distinct_id=_clean_distinct_id(distinct_id),
            properties=_sanitize_properties(properties),
        )
    except Exception:
        LOGGER.exception("posthog_capture_failed")


def capture_exception(
    exc: BaseException,
    *,
    distinct_id: str = "anonymous",
    properties: dict[str, Any] | None = None,
) -> None:
    if not is_enabled():
        return
    try:
        _client.capture_exception(  # type: ignore[union-attr]
            exc,
            distinct_id=_clean_distinct_id(distinct_id),
            properties=_sanitize_properties(properties),
        )
    except Exception:
        LOGGER.exception("posthog_capture_exception_failed")


def distinct_id_from_request(request: Any) -> str:
    state = getattr(request, "state", None)
    headers = getattr(request, "headers", {})
    return (
        headers.get("x-user-id")
        or headers.get("x-posthog-distinct-id")
        or headers.get("x-session-id")
        or getattr(state, "user_id", "")
        or "anonymous"
    )


def should_track_request_path(path: str) -> bool:
    return not (
        path.startswith("/health")
        or path.startswith("/static")
        or path == "/posthog.js"
        or path.startswith("/favicon")
    )


def request_properties(request: Any, *, status_code: int, latency_ms: int) -> dict[str, Any]:
    state = getattr(request, "state", None)
    headers = getattr(request, "headers", {})
    return {
        "method": getattr(request, "method", ""),
        "path": getattr(getattr(request, "url", None), "path", ""),
        "status_code": status_code,
        "latency_ms": latency_ms,
        "request_id": getattr(state, "request_id", headers.get("x-request-id", "")),
    }


def capture_request_completed(request: Any, response: Any, latency_ms: int) -> None:
    path = getattr(getattr(request, "url", None), "path", "")
    if not should_track_request_path(path):
        return
    capture(
        distinct_id=distinct_id_from_request(request),
        event="api request completed",
        properties=request_properties(request, status_code=getattr(response, "status_code", 0), latency_ms=latency_ms),
    )


def capture_request_error(request: Any, error: BaseException, latency_ms: int) -> None:
    path = getattr(getattr(request, "url", None), "path", "")
    if not should_track_request_path(path):
        return
    properties = request_properties(request, status_code=500, latency_ms=latency_ms)
    properties["error_type"] = type(error).__name__
    distinct_id = distinct_id_from_request(request)
    capture_exception(error, distinct_id=distinct_id, properties=properties)
    capture(distinct_id=distinct_id, event="api request errored", properties=properties)


def estimate_tokens(value: Any) -> int:
    if value is None:
        return 0
    if not isinstance(value, str):
        value = str(value)
    text = value.strip()
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def provider_from_model(model: str) -> str:
    value = str(model or "").strip().lower()
    if ":" in value:
        return value.split(":", 1)[0] or "unknown"
    if "gemini" in value:
        return "gemini"
    if "ollama" in value or value.startswith(("llama", "qwen", "mistral", "gemma")):
        return "ollama"
    if "groq" in value:
        return "groq"
    if "openrouter" in value:
        return "openrouter"
    if "pollinations" in value:
        return "pollinations"
    return "nexora" if value.startswith("nexora") else "unknown"


def capture_ai_generation(
    *,
    distinct_id: str = "anonymous",
    trace_id: str,
    model: str,
    provider: str | None = None,
    input_text: str | None = None,
    output_text: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: int | None = None,
    error: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if not _ai_observability_enabled:
        return

    resolved_provider = provider or provider_from_model(model)
    prompt_tokens = input_tokens if input_tokens is not None else estimate_tokens(input_text)
    completion_tokens = output_tokens if output_tokens is not None else estimate_tokens(output_text)
    properties: dict[str, Any] = {
        "$ai_trace_id": trace_id,
        "$ai_model": model or "unknown",
        "$ai_provider": resolved_provider,
        "$ai_input_tokens": prompt_tokens,
        "$ai_output_tokens": completion_tokens,
        "$ai_latency": round((latency_ms or 0) / 1000, 4),
        "$ai_is_error": bool(error),
        "latency_ms": latency_ms or 0,
        "token_estimate_source": "software_estimate",
        **(metadata or {}),
    }
    if session_id:
        properties["$ai_session_id"] = session_id
    if error:
        properties["$ai_error"] = str(error)[:1000]
    if _capture_prompts and input_text is not None:
        properties["$ai_input"] = [{"role": "user", "content": input_text[:8000]}]
    if _capture_responses and output_text is not None:
        properties["$ai_output_choices"] = [{"role": "assistant", "content": output_text[:8000]}]

    try:
        ai_observability_store.record_ai_request(
            distinct_id=distinct_id,
            trace_id=trace_id,
            model=model or "unknown",
            provider=resolved_provider,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            latency_ms=latency_ms or 0,
            error=error,
            session_id=session_id,
            metadata=metadata or {},
        )
    except Exception:
        LOGGER.exception("ai_observability_store_record_failed")

    if not is_enabled():
        return

    capture(distinct_id=distinct_id, event="$ai_generation", properties=properties)


def capture_feature_usage(
    distinct_id: str,
    feature: str,
    properties: dict[str, Any] | None = None,
) -> None:
    capture(
        distinct_id=distinct_id,
        event="feature used",
        properties={"feature": feature, **(properties or {})},
    )


def capture_signup(
    distinct_id: str,
    properties: dict[str, Any] | None = None,
) -> None:
    capture(
        distinct_id=distinct_id,
        event="user signed up",
        properties=properties or {},
    )


def capture_install(
    distinct_id: str = "anonymous",
    properties: dict[str, Any] | None = None,
) -> None:
    capture(
        distinct_id=distinct_id,
        event="software installed",
        properties=properties or {},
    )
