from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "nexora_data"
LOCK = threading.RLock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def data_dir() -> Path:
    return Path(os.getenv("NEXORA_DATA_DIR", str(DEFAULT_DATA_DIR)))


def store_path() -> Path:
    return data_dir() / "customer_dashboard.json"


def default_store() -> dict[str, Any]:
    return {"api_keys": [], "updated_at": now_iso()}


def load_store() -> dict[str, Any]:
    with LOCK:
        path = store_path()
        if not path.exists():
            return default_store()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default_store()
        if not isinstance(data, dict):
            return default_store()
        data.setdefault("api_keys", [])
        return data


def save_store(data: dict[str, Any]) -> None:
    with LOCK:
        path = store_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data["updated_at"] = now_iso()
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def public_key_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id", ""),
        "name": record.get("name", ""),
        "key_prefix": record.get("key_prefix", ""),
        "created_at": record.get("created_at", ""),
        "last_used_at": record.get("last_used_at", ""),
        "revoked": bool(record.get("revoked")),
    }


def create_api_key(user_id: str, name: str = "Default key") -> dict[str, Any]:
    clean_name = str(name or "Default key").strip()[:80] or "Default key"
    full_key = "sw_live_" + secrets.token_urlsafe(32).replace("-", "").replace("_", "")[:40]
    now = now_iso()
    record = {
        "id": f"key_{uuid.uuid4().hex[:12]}",
        "user_id": str(user_id),
        "name": clean_name,
        "key_prefix": full_key[:14],
        "key_hash": hash_key(full_key),
        "created_at": now,
        "last_used_at": "",
        "revoked": False,
    }
    data = load_store()
    keys = [item for item in data.get("api_keys", []) if isinstance(item, dict)]
    keys.append(record)
    data["api_keys"] = keys[-5000:]
    save_store(data)
    return {"api_key": full_key, "record": public_key_record(record)}


def list_api_keys(user_id: str) -> list[dict[str, Any]]:
    keys = [
        public_key_record(item)
        for item in load_store().get("api_keys", [])
        if isinstance(item, dict) and str(item.get("user_id", "")) == str(user_id)
    ]
    keys.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return keys


def revoke_api_key(user_id: str, key_id: str) -> bool:
    data = load_store()
    changed = False
    for item in data.get("api_keys", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("user_id", "")) == str(user_id) and str(item.get("id", "")) == str(key_id):
            item["revoked"] = True
            item["updated_at"] = now_iso()
            changed = True
    if changed:
        save_store(data)
    return changed


def authenticate_api_key(api_key: str) -> dict[str, Any] | None:
    candidate = str(api_key or "").strip()
    if not candidate:
        return None
    digest = hash_key(candidate)
    data = load_store()
    matched: dict[str, Any] | None = None
    for item in data.get("api_keys", []):
        if not isinstance(item, dict) or item.get("revoked"):
            continue
        if item.get("key_hash") == digest:
            item["last_used_at"] = now_iso()
            matched = item
            break
    if matched:
        save_store(data)
        return dict(matched)
    return None
