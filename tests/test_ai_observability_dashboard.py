from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"


class FakeSupabaseAuthError(RuntimeError):
    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class FakeSupabaseAuthClient:
    configured = True

    def __init__(self) -> None:
        self.users = {
            "alice-token": {
                "id": "auth_alice",
                "email": "alice@example.com",
                "user_metadata": {"name": "Alice"},
                "email_confirmed_at": "2026-08-07T00:00:00+00:00",
                "created_at": "2026-08-07T00:00:00+00:00",
            },
            "bob-token": {
                "id": "auth_bob",
                "email": "bob@example.com",
                "user_metadata": {"name": "Bob"},
                "email_confirmed_at": "2026-08-07T00:00:00+00:00",
                "created_at": "2026-08-07T00:00:00+00:00",
            },
        }

    def get_user(self, access_token: str) -> Dict[str, Any]:
        user = self.users.get(access_token)
        if not user:
            raise FakeSupabaseAuthError("Invalid token")
        return user


def auth_headers(token: str = "alice-token") -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@contextmanager
def patched_env(values: Dict[str, str], unset: Iterable[str] = ()):
    keys = set(values) | set(unset)
    original: Dict[str, Optional[str]] = {key: os.environ.get(key) for key in keys}
    try:
        for key in unset:
            os.environ.pop(key, None)
        for key, value in values.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def clear_backend_modules() -> None:
    for name in list(sys.modules):
        if (
            name == "routes"
            or name.startswith("routes.")
            or name
            in {
                "runtime",
                "config",
                "database",
                "dependencies",
                "observability",
                "exception_handlers",
                "health",
                "posthog_client",
                "ai_observability_store",
                "customer_dashboard_store",
                "onboarding_store",
            }
        ):
            sys.modules.pop(name, None)


def import_backend_main(name: str):
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    clear_backend_modules()
    spec = importlib.util.spec_from_file_location(name, BACKEND_DIR / "main.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    module.SupabaseAuthError = FakeSupabaseAuthError
    module.supabase_auth_client = FakeSupabaseAuthClient()
    return module


class AIObservabilityDashboardTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_backend_modules()

    def test_dashboard_page_and_api_are_available(self):
        with tempfile.TemporaryDirectory() as data_dir:
            with patched_env(
                {
                    "NEXORA_ENV": "test",
                    "NEXORA_DATA_DIR": data_dir,
                    "NEXORA_NATIVE_CORE_LOOP": "false",
                    "POSTHOG_ENABLED": "false",
                    "SUPABASE_URL": "https://unit-test.supabase.co",
                    "SUPABASE_ANON_KEY": "anon-test-key",
                },
                unset=["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "POSTHOG_PROJECT_API_KEY"],
            ):
                module = import_backend_main("backend_main_ai_observability_page_test")
                with TestClient(module.app) as client:
                    page = client.get("/observability")
                    anonymous_meta = client.get("/api/observability")
                    anonymous_overview = client.get("/api/observability/overview")
                    meta = client.get("/api/observability", headers=auth_headers())
                    overview = client.get("/api/observability/overview", headers=auth_headers())

                self.assertEqual(page.status_code, 200)
                self.assertIn("AI observability dashboard", page.text)
                self.assertEqual(anonymous_meta.status_code, 401)
                self.assertEqual(anonymous_overview.status_code, 401)
                self.assertEqual(meta.status_code, 200)
                self.assertEqual(meta.json()["dashboard"], "/observability")
                self.assertEqual(overview.status_code, 200)
                self.assertEqual(overview.json()["summary"]["requests"], 0)

    def test_demo_event_populates_requests_traces_sessions_and_alerts(self):
        with tempfile.TemporaryDirectory() as data_dir:
            with patched_env(
                {
                    "NEXORA_ENV": "test",
                    "NEXORA_DATA_DIR": data_dir,
                    "NEXORA_NATIVE_CORE_LOOP": "false",
                    "POSTHOG_ENABLED": "false",
                    "SUPABASE_URL": "https://unit-test.supabase.co",
                    "SUPABASE_ANON_KEY": "anon-test-key",
                },
                unset=["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "POSTHOG_PROJECT_API_KEY"],
            ):
                module = import_backend_main("backend_main_ai_observability_demo_test")
                with TestClient(module.app) as client:
                    created = client.post("/api/observability/demo", headers=auth_headers())
                    overview = client.get("/api/observability/overview", headers=auth_headers())
                    requests = client.get("/api/observability/requests", headers=auth_headers())
                    traces = client.get("/api/observability/traces", headers=auth_headers())
                    sessions = client.get("/api/observability/sessions", headers=auth_headers())
                    alerts = client.post(
                        "/api/observability/alerts",
                        headers=auth_headers(),
                        json={
                            "enabled": True,
                            "latency_ms_threshold": 1000,
                            "error_rate_threshold": 0.5,
                            "token_usage_threshold": 1000,
                            "notify_email": "ops@example.com",
                            "webhook_url": "https://example.com/hook",
                        },
                    )
                    bob_alerts = client.get("/api/observability/alerts", headers=auth_headers("bob-token"))

                self.assertEqual(created.status_code, 200)
                self.assertEqual(overview.json()["summary"]["requests"], 1)
                self.assertEqual(overview.json()["summary"]["total_tokens"], 1180)
                self.assertEqual(len(requests.json()["requests"]), 1)
                self.assertEqual(len(traces.json()["traces"]), 1)
                self.assertEqual(len(sessions.json()["sessions"]), 1)
                active_alerts = alerts.json()["active_alerts"]
                self.assertTrue(any(item["type"] == "latency" for item in active_alerts))
                self.assertTrue(any(item["type"] == "tokens" for item in active_alerts))
                self.assertEqual(bob_alerts.json()["settings"]["notify_email"], "")
                self.assertEqual(bob_alerts.json()["settings"]["webhook_url"], "")

    def test_chat_ai_observability_records_without_posthog_keys(self):
        with tempfile.TemporaryDirectory() as data_dir:
            with patched_env(
                {
                    "NEXORA_ENV": "test",
                    "NEXORA_DATA_DIR": data_dir,
                    "NEXORA_NATIVE_CORE_LOOP": "false",
                    "POSTHOG_ENABLED": "false",
                    "SUPABASE_URL": "https://unit-test.supabase.co",
                    "SUPABASE_ANON_KEY": "anon-test-key",
                },
                unset=["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "POSTHOG_PROJECT_API_KEY"],
            ):
                module = import_backend_main("backend_main_ai_observability_chat_test")
                with TestClient(module.app) as client:
                    chat = client.post(
                        "/chat",
                        headers=auth_headers(),
                        json={"message": "hello", "session_id": "session_observability_test"},
                    )
                    requests = client.get("/api/observability/requests", headers=auth_headers())

                self.assertEqual(chat.status_code, 200)
                items = requests.json()["requests"]
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["session_id"], "session_observability_test")
                self.assertGreaterEqual(items[0]["total_tokens"], 1)

    def test_stored_xss_chain_requires_login_is_user_scoped_and_uses_safe_dom_rendering(self):
        marker = '<img src=x onerror="window.__xss=true">'
        with tempfile.TemporaryDirectory() as data_dir:
            with patched_env(
                {
                    "NEXORA_ENV": "test",
                    "NEXORA_DATA_DIR": data_dir,
                    "NEXORA_NATIVE_CORE_LOOP": "false",
                    "POSTHOG_ENABLED": "false",
                    "SUPABASE_URL": "https://unit-test.supabase.co",
                    "SUPABASE_ANON_KEY": "anon-test-key",
                },
                unset=["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "POSTHOG_PROJECT_API_KEY"],
            ):
                module = import_backend_main("backend_main_ai_observability_xss_test")
                with TestClient(module.app) as client:
                    anonymous_key = client.post(
                        "/api/onboarding/generate-key",
                        json={"framework": "JavaScript", "onboarding_id": "xss-test"},
                    )
                    created = client.post(
                        "/api/onboarding/generate-key",
                        headers=auth_headers(),
                        json={"framework": "JavaScript", "onboarding_id": "xss-test"},
                    )
                    api_key = created.json()["api_key"]
                    ingest = client.post(
                        "/api/events/ingest",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "project_id": "xss-test",
                            "event_type": "agent_run",
                            "model": marker,
                            "provider": marker,
                            "latency_ms": 1,
                            "success": True,
                        },
                    )
                    anonymous_read = client.get("/api/observability/requests")
                    alice_read = client.get("/api/observability/requests", headers=auth_headers())
                    bob_read = client.get("/api/observability/requests", headers=auth_headers("bob-token"))

                self.assertEqual(anonymous_key.status_code, 401)
                self.assertEqual(created.status_code, 200, created.text)
                self.assertEqual(ingest.status_code, 200, ingest.text)
                self.assertEqual(anonymous_read.status_code, 401)
                self.assertEqual(alice_read.json()["requests"][0]["model"], marker)
                self.assertEqual(bob_read.json()["requests"], [])

        page = (ROOT_DIR / "frontend" / "observability.html").read_text(encoding="utf-8")
        self.assertNotIn('$("requestsBody").innerHTML', page)
        self.assertNotIn('$("tracesRows").innerHTML', page)
        self.assertNotIn('$("sessionsRows").innerHTML', page)
        self.assertNotIn('$("activeAlerts").innerHTML', page)
        self.assertIn("element.textContent = String(text)", page)


if __name__ == "__main__":
    unittest.main()
