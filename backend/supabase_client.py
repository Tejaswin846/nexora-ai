from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse, urlunparse

import requests


class SupabaseAuthError(RuntimeError):
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
        raise SupabaseAuthError("SUPABASE_URL must be a full https://...supabase.co URL.", status_code=500)
    path = parsed.path.rstrip("/")
    if path.endswith("/rest/v1"):
        path = path[: -len("/rest/v1")]
    elif path == "/rest/v1":
        path = ""
    elif "/rest/v1/" in f"{path}/":
        raise SupabaseAuthError("SUPABASE_URL must not include /rest/v1/.", status_code=500)
    return urlunparse((parsed.scheme, parsed.netloc, path.rstrip("/"), "", "", "")).rstrip("/")


@dataclass
class SupabaseConfig:
    url: str
    anon_key: str
    service_role_key: str = ""
    timeout: float = 12.0

    @classmethod
    def from_env(cls) -> "SupabaseConfig":
        timeout = float(os.getenv("SUPABASE_AUTH_TIMEOUT", "12"))
        return cls(
            url=normalize_supabase_url(os.getenv("SUPABASE_URL", "")),
            anon_key=os.getenv("SUPABASE_ANON_KEY", "").strip(),
            service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
            timeout=timeout,
        )

    @property
    def configured(self) -> bool:
        return bool(self.url and self.anon_key)


class SupabaseAuthClient:
    def __init__(self, config: Optional[SupabaseConfig] = None, session: Optional[requests.Session] = None) -> None:
        self.config = config or SupabaseConfig.from_env()
        self.session = session or requests.Session()

    @property
    def configured(self) -> bool:
        return self.config.configured

    def public_config(self) -> Dict[str, Any]:
        return {
            "configured": self.config.configured,
            "supabase_url": self.config.url,
            "supabase_anon_key": self.config.anon_key,
        }

    def _require_config(self) -> None:
        if not self.config.url:
            raise SupabaseAuthError("SUPABASE_URL is not configured.", status_code=503)
        if not self.config.anon_key:
            raise SupabaseAuthError("SUPABASE_ANON_KEY is not configured.", status_code=503)

    def _auth_url(self, path: str) -> str:
        self._require_config()
        return f"{self.config.url}/auth/v1/{path.lstrip('/')}"

    def _headers(self, token: Optional[str] = None, service_role: bool = False) -> Dict[str, str]:
        key = self.config.service_role_key if service_role else self.config.anon_key
        if service_role and not key:
            raise SupabaseAuthError("SUPABASE_SERVICE_ROLE_KEY is not configured.", status_code=503)
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {token or key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: Optional[str] = None,
        service_role: bool = False,
        json_payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        response = self.session.request(
            method,
            self._auth_url(path),
            headers=self._headers(token=token, service_role=service_role),
            json=json_payload,
            params=params,
            timeout=self.config.timeout,
        )
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = {"message": response.text}
        if response.status_code >= 400:
            message = (
                payload.get("msg")
                or payload.get("message")
                or payload.get("error_description")
                or payload.get("error")
                or f"Supabase Auth returned HTTP {response.status_code}."
            )
            raise SupabaseAuthError(str(message), status_code=response.status_code, payload=payload)
        return payload if isinstance(payload, dict) else {"data": payload}

    def sign_up(self, email: str, password: str, name: str, redirect_to: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "email": email,
            "password": password,
            "data": {"name": name},
        }
        if redirect_to:
            payload["options"] = {"email_redirect_to": redirect_to}
        return self._request("POST", "signup", json_payload=payload)

    def sign_in_with_password(self, email: str, password: str) -> Dict[str, Any]:
        return self._request(
            "POST",
            "token",
            params={"grant_type": "password"},
            json_payload={"email": email, "password": password},
        )

    def recover_password(self, email: str, redirect_to: str) -> Dict[str, Any]:
        return self._request(
            "POST",
            "recover",
            json_payload={"email": email},
            params={"redirect_to": redirect_to},
        )

    def get_user(self, access_token: str) -> Dict[str, Any]:
        return self._request("GET", "user", token=access_token)

    def update_password(self, access_token: str, new_password: str) -> Dict[str, Any]:
        return self._request("PUT", "user", token=access_token, json_payload={"password": new_password})

    def logout(self, access_token: str) -> Dict[str, Any]:
        return self._request("POST", "logout", token=access_token)

    def admin_get_user(self, user_id: str) -> Dict[str, Any]:
        return self._request("GET", f"admin/users/{user_id}", service_role=True)
