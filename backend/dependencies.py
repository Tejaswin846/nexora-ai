from __future__ import annotations

from typing import Any, Callable, Iterator

from fastapi import Request

try:
    from config import Settings, get_settings
    from database import DatabaseSession, session_scope
    from supabase_client import SupabaseAuthClient
except Exception:
    from .config import Settings, get_settings
    from .database import DatabaseSession, session_scope
    from .supabase_client import SupabaseAuthClient


def get_runtime_module():
    try:
        import runtime
    except Exception:
        from . import runtime
    return runtime


def get_db() -> Iterator[DatabaseSession]:
    yield from session_scope(get_settings())


def get_current_user(request: Request) -> dict[str, Any]:
    return get_runtime_module().require_authenticated_user(request)


def get_rate_limiter() -> Callable[[Request], dict[str, Any]]:
    return get_runtime_module().check_rate_limit


def get_supabase() -> SupabaseAuthClient:
    return get_runtime_module().supabase_auth_client


def get_runtime_settings() -> Settings:
    return get_settings()
