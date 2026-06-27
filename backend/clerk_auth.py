from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from jose import JWTError, jwt


class ClerkAuthError(RuntimeError):
    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class ClerkConfig:
    secret_key: str
    publishable_key: str
    jwt_issuer: str
    webhook_secret: str
    jwks_url: str
    timeout: float = 10.0

    @classmethod
    def from_env(cls) -> "ClerkConfig":
        issuer = os.getenv("CLERK_JWT_ISSUER", "").strip().rstrip("/")
        jwks_url = os.getenv("CLERK_JWKS_URL", "").strip()
        if not jwks_url and issuer:
            jwks_url = f"{issuer}/.well-known/jwks.json"
        return cls(
            secret_key=os.getenv("CLERK_SECRET_KEY", "").strip(),
            publishable_key=os.getenv("CLERK_PUBLISHABLE_KEY", "").strip(),
            jwt_issuer=issuer,
            webhook_secret=os.getenv("CLERK_WEBHOOK_SECRET", "").strip(),
            jwks_url=jwks_url,
            timeout=float(os.getenv("CLERK_AUTH_TIMEOUT", "10")),
        )

    @property
    def configured(self) -> bool:
        return bool(self.publishable_key and self.jwt_issuer and self.jwks_url)


@dataclass
class ClerkUserContext:
    user_id: str
    email: str = ""
    name: str = ""
    session_id: str = ""
    claims: Dict[str, Any] = None

    def to_profile(self) -> Dict[str, Any]:
        return {
            "id": self.user_id,
            "email": self.email,
            "name": self.name,
            "session_id": self.session_id,
            "auth_provider": "clerk",
            "claims": self.claims or {},
        }


class ClerkJWTVerifier:
    def __init__(self, config: Optional[ClerkConfig] = None, session: Optional[requests.Session] = None) -> None:
        self.config = config or ClerkConfig.from_env()
        self.session = session or requests.Session()
        self._jwks: Optional[Dict[str, Any]] = None
        self._jwks_loaded_at = 0.0

    @property
    def configured(self) -> bool:
        return self.config.configured

    def public_config(self) -> Dict[str, Any]:
        return {
            "provider": "clerk",
            "configured": self.config.configured,
            "clerk_publishable_key": self.config.publishable_key,
            "clerk_jwt_issuer": self.config.jwt_issuer,
        }

    def _jwks(self) -> Dict[str, Any]:
        if self._jwks and time.time() - self._jwks_loaded_at < 300:
            return self._jwks
        if not self.config.jwks_url:
            raise ClerkAuthError("CLERK_JWT_ISSUER or CLERK_JWKS_URL is not configured.", status_code=503)
        response = self.session.get(self.config.jwks_url, timeout=self.config.timeout)
        if response.status_code >= 400:
            raise ClerkAuthError(f"Could not fetch Clerk JWKS: HTTP {response.status_code}.", status_code=503)
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
            raise ClerkAuthError("Clerk JWKS response was invalid.", status_code=503)
        self._jwks = payload
        self._jwks_loaded_at = time.time()
        return payload

    def verify_token(self, token: str) -> ClerkUserContext:
        if not token:
            raise ClerkAuthError("Missing Clerk session token.")
        if not self.configured:
            raise ClerkAuthError("Clerk authentication is not configured.", status_code=503)
        try:
            header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise ClerkAuthError("Invalid Clerk session token.") from exc
        key_id = header.get("kid")
        keys = self._jwks().get("keys", [])
        key = next((item for item in keys if item.get("kid") == key_id), None)
        if key is None and len(keys) == 1:
            key = keys[0]
        if not key:
            self._jwks = None
            key = next((item for item in self._jwks().get("keys", []) if item.get("kid") == key_id), None)
        if not key:
            raise ClerkAuthError("Clerk signing key was not found.")
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[header.get("alg") or "RS256"],
                issuer=self.config.jwt_issuer,
                options={"verify_aud": False},
            )
        except JWTError as exc:
            raise ClerkAuthError("Invalid or expired Clerk session token.") from exc
        user_id = str(claims.get("sub") or "").strip()
        if not user_id:
            raise ClerkAuthError("Clerk token did not include a user id.")
        email = str(
            claims.get("email")
            or claims.get("email_address")
            or claims.get("primary_email_address")
            or ""
        )
        first = str(claims.get("given_name") or claims.get("first_name") or "").strip()
        last = str(claims.get("family_name") or claims.get("last_name") or "").strip()
        name = str(claims.get("name") or " ".join(part for part in [first, last] if part)).strip()
        return ClerkUserContext(
            user_id=user_id,
            email=email,
            name=name,
            session_id=str(claims.get("sid") or ""),
            claims=claims,
        )


def bearer_token_from_header(value: str) -> str:
    auth_header = value or ""
    if not auth_header.lower().startswith("bearer "):
        return ""
    return auth_header.split(" ", 1)[1].strip()
