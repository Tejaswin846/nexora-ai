from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse, urlunparse

import requests


class SupabaseStorageError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400, payload: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}


def normalize_supabase_url(raw_url: str) -> str:
    value = (raw_url or "").strip().rstrip("/")
    if not value:
        return ""
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise SupabaseStorageError("SUPABASE_URL must be a full https://...supabase.co URL.", status_code=500)
    path = parsed.path.rstrip("/")
    if path.endswith("/rest/v1"):
        path = path[: -len("/rest/v1")]
    elif path == "/rest/v1":
        path = ""
    elif "/rest/v1/" in f"{path}/":
        raise SupabaseStorageError("SUPABASE_URL must not include /rest/v1/.", status_code=500)
    return urlunparse((parsed.scheme, parsed.netloc, path.rstrip("/"), "", "", "")).rstrip("/")


@dataclass
class SupabaseConfig:
    url: str
    service_role_key: str = ""
    timeout: float = 12.0

    @classmethod
    def from_env(cls) -> "SupabaseConfig":
        timeout = float(os.getenv("SUPABASE_STORAGE_TIMEOUT", "12"))
        return cls(
            url=normalize_supabase_url(os.getenv("SUPABASE_URL", "")),
            service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
            timeout=timeout,
        )

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_role_key)


class SupabaseStorageClient:
    def __init__(self, config: Optional[SupabaseConfig] = None, session: Optional[requests.Session] = None) -> None:
        self.config = config or SupabaseConfig.from_env()
        self.session = session or requests.Session()

    @property
    def configured(self) -> bool:
        return self.config.configured

    def _headers(self) -> Dict[str, str]:
        if not self.config.url:
            raise SupabaseStorageError("SUPABASE_URL is not configured.", status_code=503)
        if not self.config.service_role_key:
            raise SupabaseStorageError("SUPABASE_SERVICE_ROLE_KEY is not configured.", status_code=503)
        return {
            "apikey": self.config.service_role_key,
            "Authorization": f"Bearer {self.config.service_role_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        }

    def rest_url(self, table: str) -> str:
        clean_table = table.strip().strip("/")
        return f"{self.config.url}/rest/v1/{clean_table}"

    def upsert(self, table: str, payload: Dict[str, Any], on_conflict: str = "id") -> Dict[str, Any]:
        response = self.session.post(
            self.rest_url(table),
            headers=self._headers(),
            params={"on_conflict": on_conflict},
            json=payload,
            timeout=self.config.timeout,
        )
        try:
            data = response.json() if response.content else {}
        except ValueError:
            data = {"message": response.text}
        if response.status_code >= 400:
            message = (
                data.get("message")
                if isinstance(data, dict)
                else None
            ) or f"Supabase storage returned HTTP {response.status_code}."
            raise SupabaseStorageError(str(message), status_code=response.status_code, payload=data if isinstance(data, dict) else {})
        return data if isinstance(data, dict) else {"data": data}

    def upsert_user_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        table = os.getenv("SUPABASE_USER_PROFILES_TABLE", "user_profiles")
        return self.upsert(table, profile, on_conflict="id")
