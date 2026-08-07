from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "nexora_data"
MAX_EVENTS = 1000
STORE_LOCK = threading.RLock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def data_dir() -> Path:
    return Path(os.getenv("NEXORA_DATA_DIR", str(DEFAULT_DATA_DIR)))


def store_path() -> Path:
    return data_dir() / "ai_observability.json"


def default_alert_settings() -> dict[str, Any]:
    return {
        "enabled": True,
        "latency_ms_threshold": 5000,
        "error_rate_threshold": 0.1,
        "token_usage_threshold": 8000,
        "notify_email": "",
        "webhook_url": "",
        "updated_at": now_iso(),
    }


def default_store() -> dict[str, Any]:
    return {
        "events": [],
        "alerts": default_alert_settings(),
        "alerts_by_user": {},
        "updated_at": now_iso(),
    }


def safe_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:2000]


def sanitize_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key)[:120]: sanitize_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_metadata(item) for item in value[:50]]
    return safe_scalar(value)


def load_store() -> dict[str, Any]:
    with STORE_LOCK:
        path = store_path()
        if not path.exists():
            return default_store()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default_store()
        if not isinstance(data, dict):
            return default_store()
        data.setdefault("events", [])
        data.setdefault("alerts", default_alert_settings())
        data.setdefault("alerts_by_user", {})
        return data


def save_store(data: dict[str, Any]) -> None:
    with STORE_LOCK:
        path = store_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data["updated_at"] = now_iso()
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def record_ai_request(
    *,
    distinct_id: str,
    trace_id: str,
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    error: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "id": f"ai_req_{uuid.uuid4().hex[:12]}",
        "trace_id": trace_id or f"trace_{uuid.uuid4().hex[:12]}",
        "session_id": session_id or "anonymous",
        "distinct_id": distinct_id or "anonymous",
        "provider": provider or "unknown",
        "model": model or "unknown",
        "latency_ms": int(latency_ms or 0),
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "total_tokens": int(input_tokens or 0) + int(output_tokens or 0),
        "success": not bool(error),
        "error": str(error)[:1000] if error else None,
        "route": (metadata or {}).get("route", ""),
        "mode": (metadata or {}).get("mode", ""),
        "metadata": sanitize_metadata(metadata or {}),
        "timeline": [
            {"step": "AI request observed", "status": "completed", "at": now_iso()},
            {"step": "Latency measured", "status": "completed", "at": now_iso()},
            {"step": "Token usage estimated", "status": "completed", "at": now_iso()},
            {
                "step": "Error check completed",
                "status": "failed" if error else "completed",
                "at": now_iso(),
            },
            {"step": "Dashboard event stored", "status": "completed", "at": now_iso()},
        ],
        "created_at": now_iso(),
    }
    data = load_store()
    events = [item for item in data.get("events", []) if isinstance(item, dict)]
    events.append(event)
    data["events"] = events[-MAX_EVENTS:]
    save_store(data)
    return event


def event_belongs_to_user(event: Mapping[str, Any], user_id: str | None = None) -> bool:
    if not user_id:
        return True
    expected = str(user_id)
    if str(event.get("distinct_id") or "") == expected:
        return True
    metadata = event.get("metadata") if isinstance(event.get("metadata"), Mapping) else {}
    return str(metadata.get("user_id") or "") == expected


def list_events(limit: int = 100, user_id: str | None = None) -> list[dict[str, Any]]:
    events = [item for item in load_store().get("events", []) if isinstance(item, dict)]
    events = [item for item in events if event_belongs_to_user(item, user_id)]
    events.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return events[: max(1, min(limit, MAX_EVENTS))]


def percentile(values: list[int], ratio: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return int(ordered[index])


def provider_breakdown(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for event in events:
        provider = str(event.get("provider") or "unknown")
        stats = grouped.setdefault(provider, {"provider": provider, "requests": 0, "errors": 0, "tokens": 0})
        stats["requests"] += 1
        stats["tokens"] += int(event.get("total_tokens") or 0)
        if not event.get("success", True):
            stats["errors"] += 1
    return sorted(grouped.values(), key=lambda item: item["requests"], reverse=True)


def overview(user_id: str | None = None) -> dict[str, Any]:
    events = list_events(MAX_EVENTS, user_id=user_id)
    latencies = [int(event.get("latency_ms") or 0) for event in events]
    errors = [event for event in events if not event.get("success", True)]
    total_tokens = sum(int(event.get("total_tokens") or 0) for event in events)
    sessions = {str(event.get("session_id") or "anonymous") for event in events}
    traces = {str(event.get("trace_id") or "") for event in events if event.get("trace_id")}
    request_count = len(events)
    return {
        "ok": True,
        "summary": {
            "requests": request_count,
            "errors": len(errors),
            "error_rate": round(len(errors) / request_count, 4) if request_count else 0,
            "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
            "p95_latency_ms": percentile(latencies, 0.95),
            "total_tokens": total_tokens,
            "sessions": len(sessions),
            "traces": len(traces),
            "last_event_at": events[0].get("created_at") if events else None,
        },
        "providers": provider_breakdown(events),
        "active_alerts": active_alerts(events, user_id=user_id),
    }


def traces(limit: int = 50, user_id: str | None = None) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for event in list_events(MAX_EVENTS, user_id=user_id):
        trace_id = str(event.get("trace_id") or "unknown")
        item = grouped.setdefault(
            trace_id,
            {
                "trace_id": trace_id,
                "session_id": event.get("session_id") or "anonymous",
                "requests": 0,
                "errors": 0,
                "latency_ms": 0,
                "tokens": 0,
                "started_at": event.get("created_at"),
                "latest_at": event.get("created_at"),
                "events": [],
            },
        )
        item["requests"] += 1
        item["latency_ms"] += int(event.get("latency_ms") or 0)
        item["tokens"] += int(event.get("total_tokens") or 0)
        item["latest_at"] = max(str(item["latest_at"]), str(event.get("created_at", "")))
        if not event.get("success", True):
            item["errors"] += 1
        item["events"].append(event)
    items = list(grouped.values())
    items.sort(key=lambda item: str(item.get("latest_at", "")), reverse=True)
    return items[: max(1, min(limit, 200))]


def sessions(limit: int = 50, user_id: str | None = None) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for event in list_events(MAX_EVENTS, user_id=user_id):
        session_id = str(event.get("session_id") or "anonymous")
        item = grouped.setdefault(
            session_id,
            {
                "session_id": session_id,
                "requests": 0,
                "errors": 0,
                "tokens": 0,
                "avg_latency_ms": 0,
                "latest_at": event.get("created_at"),
            },
        )
        item["requests"] += 1
        item["tokens"] += int(event.get("total_tokens") or 0)
        item["avg_latency_ms"] += int(event.get("latency_ms") or 0)
        item["latest_at"] = max(str(item["latest_at"]), str(event.get("created_at", "")))
        if not event.get("success", True):
            item["errors"] += 1
    items = list(grouped.values())
    for item in items:
        item["avg_latency_ms"] = int(item["avg_latency_ms"] / max(1, item["requests"]))
    items.sort(key=lambda item: str(item.get("latest_at", "")), reverse=True)
    return items[: max(1, min(limit, 200))]


def get_alert_settings(user_id: str | None = None) -> dict[str, Any]:
    data = load_store()
    if user_id:
        alerts_by_user = data.get("alerts_by_user")
        alerts = alerts_by_user.get(str(user_id)) if isinstance(alerts_by_user, Mapping) else None
    else:
        alerts = data.get("alerts")
    if not isinstance(alerts, dict):
        return default_alert_settings()
    defaults = default_alert_settings()
    defaults.update(alerts)
    return defaults


def update_alert_settings(settings: Mapping[str, Any], user_id: str | None = None) -> dict[str, Any]:
    current = get_alert_settings(user_id=user_id)
    for key in ("enabled", "latency_ms_threshold", "error_rate_threshold", "token_usage_threshold", "notify_email", "webhook_url"):
        if key in settings:
            current[key] = settings[key]
    current["enabled"] = bool(current.get("enabled"))
    current["latency_ms_threshold"] = max(0, int(current.get("latency_ms_threshold") or 0))
    current["error_rate_threshold"] = max(0.0, min(1.0, float(current.get("error_rate_threshold") or 0)))
    current["token_usage_threshold"] = max(0, int(current.get("token_usage_threshold") or 0))
    current["notify_email"] = str(current.get("notify_email") or "")[:300]
    current["webhook_url"] = str(current.get("webhook_url") or "")[:500]
    current["updated_at"] = now_iso()
    data = load_store()
    if user_id:
        alerts_by_user = data.get("alerts_by_user") if isinstance(data.get("alerts_by_user"), dict) else {}
        alerts_by_user[str(user_id)] = current
        data["alerts_by_user"] = alerts_by_user
    else:
        data["alerts"] = current
    save_store(data)
    return current


def active_alerts(events: list[dict[str, Any]] | None = None, user_id: str | None = None) -> list[dict[str, Any]]:
    settings = get_alert_settings(user_id=user_id)
    if not settings.get("enabled"):
        return []
    source = events if events is not None else list_events(MAX_EVENTS, user_id=user_id)
    alerts: list[dict[str, Any]] = []
    latency_threshold = int(settings["latency_ms_threshold"])
    error_threshold = float(settings["error_rate_threshold"])
    token_threshold = int(settings["token_usage_threshold"])
    if latency_threshold and any(int(event.get("latency_ms") or 0) >= latency_threshold for event in source):
        alerts.append({"type": "latency", "severity": "warning", "message": "Latency threshold exceeded."})
    if source and error_threshold:
        errors = [event for event in source if not event.get("success", True)]
        if len(errors) / len(source) >= error_threshold:
            alerts.append({"type": "errors", "severity": "critical", "message": "Error-rate threshold exceeded."})
    if token_threshold and any(int(event.get("total_tokens") or 0) >= token_threshold for event in source):
        alerts.append({"type": "tokens", "severity": "warning", "message": "Token usage threshold exceeded."})
    return alerts


def seed_demo_event(user_id: str = "demo-user") -> dict[str, Any]:
    return record_ai_request(
        distinct_id=user_id,
        trace_id=f"trace_demo_{uuid.uuid4().hex[:8]}",
        session_id=f"session_demo_{uuid.uuid4().hex[:6]}",
        provider="openai",
        model="gpt-4.1",
        input_tokens=420,
        output_tokens=760,
        latency_ms=1280,
        error=None,
        metadata={
            "route": "/api/observability/demo",
            "mode": "demo",
            "source": "dashboard",
            "user_id": user_id,
        },
    )
