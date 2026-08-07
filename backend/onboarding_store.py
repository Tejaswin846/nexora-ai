from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    import database
except Exception:  # pragma: no cover - package import fallback
    from . import database


LOCK = threading.RLock()
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "nexora_data"
MEMORY_STORE: dict[str, Any] = {"api_keys": [], "status": {}}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_id(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return f"onb_{uuid.uuid4().hex[:16]}"
    safe = "".join(ch for ch in text if ch.isalnum() or ch in {"_", "-"})
    return (safe or f"onb_{uuid.uuid4().hex[:16]}")[:120]


def clean_framework(value: str | None) -> str:
    return str(value or "JavaScript").strip()[:80] or "JavaScript"


def hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return "sw_onb_" + secrets.token_urlsafe(36).replace("-", "").replace("_", "")[:48]


def data_dir() -> Path:
    return Path(os.getenv("NEXORA_DATA_DIR", str(DEFAULT_DATA_DIR))).expanduser()


def fallback_path() -> Path:
    return data_dir() / "onboarding.json"


def env_name() -> str:
    return os.getenv("NEXORA_ENV", os.getenv("SOFTWARE_ENV", os.getenv("ENV", "development"))).strip().lower()


def dev_fallback_allowed() -> bool:
    return env_name() in {"development", "test", "local", ""}


def public_key_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id", ""),
        "name": record.get("name", ""),
        "key_prefix": record.get("key_prefix", ""),
        "framework": record.get("framework", ""),
        "created_at": record.get("created_at", ""),
        "last_used_at": record.get("last_used_at", ""),
        "revoked": bool(record.get("revoked")),
    }


def internal_key_record(record: Mapping[str, Any]) -> dict[str, Any]:
    item = public_key_record(record)
    item["onboarding_id"] = record.get("onboarding_id", "")
    item["user_id"] = record.get("user_id", "") or f"onboarding:{record.get('onboarding_id', '')}"
    return item


def row_to_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    mapping = getattr(row, "_mapping", None)
    if mapping is not None:
        return dict(mapping)
    return dict(row)


def ensure_schema(session: database.DatabaseSession) -> None:
    session.execute(
        """
        CREATE TABLE IF NOT EXISTS onboarding_api_keys (
            id TEXT PRIMARY KEY,
            onboarding_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            key_prefix TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            framework TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_used_at TEXT NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    session.execute(
        """
        CREATE TABLE IF NOT EXISTS onboarding_status (
            onboarding_id TEXT PRIMARY KEY,
            framework TEXT NOT NULL,
            key_id TEXT NOT NULL,
            test_event_id TEXT NOT NULL,
            verified INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NOT NULL,
            started_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT NOT NULL
        )
        """
    )
    session.execute("CREATE INDEX IF NOT EXISTS idx_onboarding_api_keys_hash ON onboarding_api_keys(key_hash)")
    session.execute("CREATE INDEX IF NOT EXISTS idx_onboarding_api_keys_onboarding ON onboarding_api_keys(onboarding_id)")
    session.commit()


def with_database() -> database.DatabaseSession:
    session = database.open_database_session()
    ensure_schema(session)
    return session


def load_fallback_store() -> dict[str, Any]:
    with LOCK:
        path = fallback_path()
        if not path.exists():
            return {"api_keys": [], "status": {}}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"api_keys": [], "status": {}}
        if not isinstance(data, dict):
            return {"api_keys": [], "status": {}}
        data.setdefault("api_keys", [])
        data.setdefault("status", {})
        return data


def save_fallback_store(data: dict[str, Any]) -> None:
    with LOCK:
        try:
            path = fallback_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            MEMORY_STORE.clear()
            MEMORY_STORE.update(data)


def fallback_create_api_key(onboarding_id: str, framework: str, name: str, full_key: str, record: dict[str, Any]) -> None:
    data = load_fallback_store()
    keys = [item for item in data.get("api_keys", []) if isinstance(item, dict)]
    keys.append(record)
    data["api_keys"] = keys[-5000:]
    status = data.get("status") if isinstance(data.get("status"), dict) else {}
    current = status.get(onboarding_id) if isinstance(status.get(onboarding_id), dict) else {}
    now = now_iso()
    status[onboarding_id] = {
        "onboarding_id": onboarding_id,
        "framework": framework,
        "key_id": record["id"],
        "test_event_id": current.get("test_event_id", ""),
        "verified": bool(current.get("verified", False)),
        "last_error": current.get("last_error", ""),
        "started_at": current.get("started_at", now),
        "updated_at": now,
        "completed_at": current.get("completed_at", ""),
    }
    data["status"] = status
    save_fallback_store(data)


def create_api_key(onboarding_id: str, framework: str, name: str = "Onboarding key") -> dict[str, Any]:
    clean_onboarding_id = clean_id(onboarding_id)
    clean_name = str(name or "Onboarding key").strip()[:80] or "Onboarding key"
    clean_framework_name = clean_framework(framework)
    full_key = generate_api_key()
    now = now_iso()
    record = {
        "id": f"onb_key_{uuid.uuid4().hex[:12]}",
        "onboarding_id": clean_onboarding_id,
        "user_id": f"onboarding:{clean_onboarding_id}",
        "name": clean_name,
        "key_prefix": full_key[:16],
        "key_hash": hash_key(full_key),
        "framework": clean_framework_name,
        "created_at": now,
        "last_used_at": "",
        "revoked": 0,
    }
    try:
        session = with_database()
        try:
            session.execute(
                """
                INSERT INTO onboarding_api_keys (
                    id, onboarding_id, user_id, name, key_prefix, key_hash, framework,
                    created_at, last_used_at, revoked
                )
                VALUES (
                    :id, :onboarding_id, :user_id, :name, :key_prefix, :key_hash, :framework,
                    :created_at, :last_used_at, :revoked
                )
                """,
                record,
            )
            upsert_status(
                clean_onboarding_id,
                framework=clean_framework_name,
                key_id=record["id"],
                verified=False,
                test_event_id="",
                last_error="",
                session=session,
            )
            session.commit()
        finally:
            session.close()
    except Exception:
        if not dev_fallback_allowed():
            raise
        fallback_create_api_key(clean_onboarding_id, clean_framework_name, clean_name, full_key, record)
    return {"api_key": full_key, "record": public_key_record(record), "onboarding_id": clean_onboarding_id}


def fallback_find_by_hash(digest: str) -> dict[str, Any] | None:
    data = load_fallback_store()
    for item in data.get("api_keys", []):
        if not isinstance(item, dict) or item.get("revoked"):
            continue
        if item.get("key_hash") == digest:
            item["last_used_at"] = now_iso()
            save_fallback_store(data)
            return internal_key_record(item)
    for item in MEMORY_STORE.get("api_keys", []):
        if isinstance(item, dict) and not item.get("revoked") and item.get("key_hash") == digest:
            item["last_used_at"] = now_iso()
            return internal_key_record(item)
    return None


def authenticate_api_key(api_key: str) -> dict[str, Any] | None:
    candidate = str(api_key or "").strip()
    if not candidate:
        return None
    digest = hash_key(candidate)
    try:
        session = with_database()
        try:
            row = session.execute(
                """
                SELECT id, onboarding_id, user_id, name, key_prefix, framework,
                       created_at, last_used_at, revoked
                FROM onboarding_api_keys
                WHERE key_hash = :key_hash AND revoked = 0
                """,
                {"key_hash": digest},
            ).fetchone()
            if row is None:
                return None
            record = row_to_dict(row)
            session.execute(
                "UPDATE onboarding_api_keys SET last_used_at = :last_used_at WHERE id = :id",
                {"last_used_at": now_iso(), "id": record["id"]},
            )
            session.commit()
            record["last_used_at"] = now_iso()
            return internal_key_record(record)
        finally:
            session.close()
    except Exception:
        if not dev_fallback_allowed():
            raise
        return fallback_find_by_hash(digest)


def upsert_status(
    onboarding_id: str,
    *,
    framework: str,
    key_id: str = "",
    verified: bool = False,
    test_event_id: str = "",
    last_error: str = "",
    session: database.DatabaseSession | None = None,
) -> dict[str, Any]:
    clean_onboarding_id = clean_id(onboarding_id)
    now = now_iso()
    completed_at = now if verified else ""
    own_session = session is None
    if session is None:
        session = with_database()
    try:
        existing = session.execute(
            "SELECT * FROM onboarding_status WHERE onboarding_id = :onboarding_id",
            {"onboarding_id": clean_onboarding_id},
        ).fetchone()
        current = row_to_dict(existing) if existing else {}
        payload = {
            "onboarding_id": clean_onboarding_id,
            "framework": clean_framework(framework or current.get("framework")),
            "key_id": key_id or current.get("key_id", ""),
            "test_event_id": test_event_id or current.get("test_event_id", ""),
            "verified": 1 if verified or bool(current.get("verified")) else 0,
            "last_error": str(last_error or "")[:1000],
            "started_at": current.get("started_at", now),
            "updated_at": now,
            "completed_at": completed_at or current.get("completed_at", ""),
        }
        if current:
            session.execute(
                """
                UPDATE onboarding_status
                SET framework = :framework, key_id = :key_id, test_event_id = :test_event_id,
                    verified = :verified, last_error = :last_error, started_at = :started_at,
                    updated_at = :updated_at, completed_at = :completed_at
                WHERE onboarding_id = :onboarding_id
                """,
                payload,
            )
        else:
            session.execute(
                """
                INSERT INTO onboarding_status (
                    onboarding_id, framework, key_id, test_event_id, verified,
                    last_error, started_at, updated_at, completed_at
                )
                VALUES (
                    :onboarding_id, :framework, :key_id, :test_event_id, :verified,
                    :last_error, :started_at, :updated_at, :completed_at
                )
                """,
                payload,
            )
        if own_session:
            session.commit()
        return public_status(payload, [])
    finally:
        if own_session:
            session.close()


def fallback_upsert_status(onboarding_id: str, **kwargs: Any) -> dict[str, Any]:
    clean_onboarding_id = clean_id(onboarding_id)
    data = load_fallback_store()
    status = data.get("status") if isinstance(data.get("status"), dict) else {}
    current = status.get(clean_onboarding_id) if isinstance(status.get(clean_onboarding_id), dict) else {}
    now = now_iso()
    verified = bool(kwargs.get("verified") or current.get("verified"))
    payload = {
        "onboarding_id": clean_onboarding_id,
        "framework": clean_framework(kwargs.get("framework") or current.get("framework")),
        "key_id": kwargs.get("key_id") or current.get("key_id", ""),
        "test_event_id": kwargs.get("test_event_id") or current.get("test_event_id", ""),
        "verified": verified,
        "last_error": str(kwargs.get("last_error") or "")[:1000],
        "started_at": current.get("started_at", now),
        "updated_at": now,
        "completed_at": now if verified else current.get("completed_at", ""),
    }
    status[clean_onboarding_id] = payload
    data["status"] = status
    save_fallback_store(data)
    return public_status(payload, fallback_keys_for(clean_onboarding_id))


def mark_test_result(
    onboarding_id: str,
    *,
    framework: str,
    key_id: str,
    event_id: str = "",
    verified: bool,
    error: str = "",
) -> dict[str, Any]:
    try:
        return upsert_status(
            onboarding_id,
            framework=framework,
            key_id=key_id,
            verified=verified,
            test_event_id=event_id,
            last_error=error,
        )
    except Exception:
        if not dev_fallback_allowed():
            raise
        return fallback_upsert_status(
            onboarding_id,
            framework=framework,
            key_id=key_id,
            verified=verified,
            test_event_id=event_id,
            last_error=error,
        )


def fallback_keys_for(onboarding_id: str) -> list[dict[str, Any]]:
    data = load_fallback_store()
    keys = [
        public_key_record(item)
        for item in data.get("api_keys", [])
        if isinstance(item, dict) and item.get("onboarding_id") == onboarding_id
    ]
    keys.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return keys


def public_status(status: Mapping[str, Any] | None, keys: list[dict[str, Any]]) -> dict[str, Any]:
    status = status or {}
    return {
        "onboarding_id": status.get("onboarding_id", ""),
        "framework": status.get("framework", ""),
        "has_api_key": bool(keys or status.get("key_id")),
        "api_keys": keys,
        "verified": bool(status.get("verified")),
        "test_event_id": status.get("test_event_id", ""),
        "last_error": status.get("last_error", ""),
        "started_at": status.get("started_at", ""),
        "updated_at": status.get("updated_at", ""),
        "completed_at": status.get("completed_at", ""),
    }


def status_for(onboarding_id: str) -> dict[str, Any]:
    clean_onboarding_id = clean_id(onboarding_id)
    try:
        session = with_database()
        try:
            status_row = session.execute(
                "SELECT * FROM onboarding_status WHERE onboarding_id = :onboarding_id",
                {"onboarding_id": clean_onboarding_id},
            ).fetchone()
            key_rows = session.execute(
                """
                SELECT id, name, key_prefix, framework, created_at, last_used_at, revoked
                FROM onboarding_api_keys
                WHERE onboarding_id = :onboarding_id
                ORDER BY created_at DESC
                """,
                {"onboarding_id": clean_onboarding_id},
            ).fetchall()
            keys = [public_key_record(row_to_dict(row)) for row in key_rows]
            if status_row:
                return public_status(row_to_dict(status_row), keys)
            return public_status({"onboarding_id": clean_onboarding_id}, keys)
        finally:
            session.close()
    except Exception:
        if not dev_fallback_allowed():
            raise
        data = load_fallback_store()
        status = {}
        if isinstance(data.get("status"), dict):
            status = data["status"].get(clean_onboarding_id, {})
        return public_status(status or {"onboarding_id": clean_onboarding_id}, fallback_keys_for(clean_onboarding_id))
