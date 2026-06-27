from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "backend"))
sys.path.insert(0, str(ROOT_DIR))


class FakeSupabaseAuthError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload: Dict[str, Any] = {}


class FakeSupabaseAuthClient:
    configured = True

    def __init__(self) -> None:
        self.users: Dict[str, Dict[str, Any]] = {}
        self.passwords: Dict[str, str] = {}
        self.sessions: Dict[str, str] = {}
        self.recovery_tokens: Dict[str, str] = {}
        self.recoveries = []
        self.fail_recovery = False

    def public_config(self) -> Dict[str, Any]:
        return {
            "configured": True,
            "supabase_url": "https://unit-test.supabase.co",
            "supabase_anon_key": "anon-test-key",
        }

    def _user_id(self, email: str) -> str:
        return f"auth_{email.split('@')[0].replace('.', '_')}"

    def _session(self, email: str, prefix: str = "token") -> Dict[str, Any]:
        token = f"{prefix}_{email}_{len(self.sessions) + 1}"
        self.sessions[token] = email
        return {
            "access_token": token,
            "refresh_token": f"refresh_{token}",
            "expires_at": 4102444800,
            "user": self.users[email],
        }

    def sign_up(self, email: str, password: str, name: str, redirect_to: Optional[str] = None) -> Dict[str, Any]:
        if email in self.users:
            raise FakeSupabaseAuthError("User already registered", 409)
        self.users[email] = {
            "id": self._user_id(email),
            "email": email,
            "user_metadata": {"name": name},
            "email_confirmed_at": "2026-06-27T00:00:00+00:00",
            "created_at": "2026-06-27T00:00:00+00:00",
        }
        self.passwords[email] = password
        return {"user": self.users[email], "session": self._session(email, "signup")}

    def sign_in_with_password(self, email: str, password: str) -> Dict[str, Any]:
        if email not in self.users or self.passwords.get(email) != password:
            raise FakeSupabaseAuthError("Invalid login credentials", 401)
        return {"user": self.users[email], "session": self._session(email, "login")}

    def recover_password(self, email: str, redirect_to: str) -> Dict[str, Any]:
        if self.fail_recovery:
            raise FakeSupabaseAuthError("SMTP provider rejected the message", 502)
        token = f"recovery_{email}"
        self.recovery_tokens[email] = token
        self.sessions[token] = email
        self.recoveries.append({"email": email, "redirect_to": redirect_to})
        return {}

    def get_user(self, access_token: str) -> Dict[str, Any]:
        if access_token == "expired-token":
            raise FakeSupabaseAuthError("JWT expired", 401)
        email = self.sessions.get(access_token)
        if not email:
            raise FakeSupabaseAuthError("Invalid token", 401)
        return self.users[email]

    def update_password(self, access_token: str, new_password: str) -> Dict[str, Any]:
        email = self.sessions.get(access_token)
        if not email:
            raise FakeSupabaseAuthError("Invalid recovery token", 401)
        self.passwords[email] = new_password
        return {"user": self.users[email]}

    def logout(self, access_token: str) -> Dict[str, Any]:
        self.sessions.pop(access_token, None)
        return {}


class AuthFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["NEXORA_DATA_DIR"] = cls.temp_dir.name
        os.environ["SUPABASE_URL"] = "https://unit-test.supabase.co"
        os.environ["SUPABASE_ANON_KEY"] = "anon-test-key"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "service-role-test-key"
        os.environ["NEXORA_PUBLIC_APP_URL"] = "https://nexora.test"
        os.environ["NEXORA_CACHE_FRONTEND_HTML"] = "false"
        spec = importlib.util.spec_from_file_location("nexora_backend_main_for_auth_tests", ROOT_DIR / "backend" / "main.py")
        assert spec and spec.loader
        cls.main = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.main
        spec.loader.exec_module(cls.main)
        cls.original_error_class = cls.main.SupabaseAuthError
        cls.main.SupabaseAuthError = FakeSupabaseAuthError
        cls.fake_auth = FakeSupabaseAuthClient()
        cls.main.supabase_auth_client = cls.fake_auth
        cls.client = TestClient(cls.main.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.main.SupabaseAuthError = cls.original_error_class
        cls.temp_dir.cleanup()

    def setUp(self) -> None:
        self.fake_auth.users.clear()
        self.fake_auth.passwords.clear()
        self.fake_auth.sessions.clear()
        self.fake_auth.recovery_tokens.clear()
        self.fake_auth.recoveries.clear()
        self.fake_auth.fail_recovery = False
        for path in [
            self.main.USERS_FILE,
            self.main.PROJECTS_FILE,
            self.main.WORKFLOWS_FILE,
            self.main.MEMORY_FILE,
            self.main.SESSIONS_FILE,
        ]:
            path.unlink(missing_ok=True)

    def signup(self, email: str = "alice@example.com", password: str = "old-password") -> Dict[str, Any]:
        response = self.client.post(
            "/auth/signup",
            json={"name": "Alice", "email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_signup_login_logout(self):
        signup_payload = self.signup()
        self.assertTrue(signup_payload["token"])
        self.assertEqual(signup_payload["user"]["email"], "alice@example.com")
        stored = self.main.load_users()[signup_payload["user"]["id"]]
        self.assertNotIn("password", stored)

        login_response = self.client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "old-password"},
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)
        token = login_response.json()["token"]

        me_response = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_response.status_code, 200)
        self.assertTrue(me_response.json()["ok"])

        logout_response = self.client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(logout_response.status_code, 200)

        invalid_me = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(invalid_me.status_code, 401)

    def test_forgot_password_sends_recovery_and_reports_send_failure(self):
        self.signup()
        response = self.client.post("/auth/forgot-password", json={"email": "alice@example.com"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.fake_auth.recoveries[0]["email"], "alice@example.com")
        self.assertEqual(self.fake_auth.recoveries[0]["redirect_to"], "https://nexora.test/reset-password")

        self.fake_auth.fail_recovery = True
        failed = self.client.post("/auth/forgot-password", json={"email": "alice@example.com"})
        self.assertEqual(failed.status_code, 502)
        self.assertIn("Password reset email was not sent", failed.text)

    def test_reset_password_invalid_and_expired_token(self):
        self.signup()
        invalid = self.client.post(
            "/auth/reset-password",
            json={"access_token": "invalid-token", "new_password": "new-password"},
        )
        self.assertEqual(invalid.status_code, 401)

        expired = self.client.get("/auth/me", headers={"Authorization": "Bearer expired-token"})
        self.assertEqual(expired.status_code, 401)
        self.assertIn("Invalid or expired session", expired.text)

    def test_reset_password_replaces_old_password(self):
        self.signup(password="old-password")
        self.client.post("/auth/forgot-password", json={"email": "alice@example.com"})
        recovery_token = self.fake_auth.recovery_tokens["alice@example.com"]

        reset = self.client.post(
            "/auth/reset-password",
            json={"access_token": recovery_token, "new_password": "new-password"},
        )
        self.assertEqual(reset.status_code, 200, reset.text)

        old_login = self.client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "old-password"},
        )
        self.assertEqual(old_login.status_code, 401)

        new_login = self.client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "new-password"},
        )
        self.assertEqual(new_login.status_code, 200, new_login.text)

    def test_per_user_data_isolation_for_projects_workflows_and_memory(self):
        alice = self.signup("alice@example.com")["token"]
        bob = self.signup("bob@example.com")["token"]

        create_project = self.client.post(
            "/projects/create",
            headers={"Authorization": f"Bearer {alice}"},
            json={"name": "Alice private project", "user_id": "auth_bob", "session_id": "alice_session"},
        )
        self.assertEqual(create_project.status_code, 200, create_project.text)
        self.assertEqual(create_project.json()["project"]["user_id"], "auth_alice")

        bob_projects = self.client.get("/projects", headers={"Authorization": f"Bearer {bob}"})
        self.assertEqual(bob_projects.status_code, 200)
        self.assertEqual(bob_projects.json()["projects"], [])

        anonymous_spoof = self.client.get("/projects?user_id=auth_alice")
        self.assertEqual(anonymous_spoof.status_code, 200)
        self.assertEqual(anonymous_spoof.json()["user_id"], "default")
        self.assertEqual(anonymous_spoof.json()["projects"], [])

        anonymous_session = self.client.get("/sessions/alice_session")
        self.assertEqual(anonymous_session.status_code, 401)
        bob_session = self.client.get("/sessions/alice_session", headers={"Authorization": f"Bearer {bob}"})
        self.assertEqual(bob_session.status_code, 403)

        create_workflow = self.client.post(
            "/workflows/create",
            headers={"Authorization": f"Bearer {alice}"},
            json={"name": "Alice workflow", "steps": ["one"], "user_id": "auth_bob"},
        )
        self.assertEqual(create_workflow.status_code, 200, create_workflow.text)

        bob_workflows = self.client.get("/workflows", headers={"Authorization": f"Bearer {bob}"})
        self.assertEqual(bob_workflows.status_code, 200)
        self.assertEqual(bob_workflows.json()["workflows"], [])

        self.main.upsert_memory_item("Alice secret", "auth_alice", "preference")
        bob_memory = self.client.get("/memory", headers={"Authorization": f"Bearer {bob}"})
        self.assertEqual(bob_memory.status_code, 200)
        self.assertEqual(bob_memory.json()["items"], [])

        anonymous_settings = self.client.post(
            "/settings/free-ai",
            json={"provider": "groq", "api_key": "should-not-save"},
        )
        self.assertEqual(anonymous_settings.status_code, 401)

        alice_settings = self.client.post(
            "/settings/free-ai",
            headers={"Authorization": f"Bearer {alice}"},
            json={"provider": "groq", "api_key": "alice-secret", "model": "llama-test"},
        )
        self.assertEqual(alice_settings.status_code, 200, alice_settings.text)
        self.assertTrue(alice_settings.json()["user_settings"]["has_api_key"])

        bob_settings = self.client.get("/settings/free-ai", headers={"Authorization": f"Bearer {bob}"})
        self.assertEqual(bob_settings.status_code, 200)
        self.assertEqual(bob_settings.json()["user_settings"]["provider"], "auto")
        self.assertFalse(bob_settings.json()["user_settings"]["has_api_key"])

    def test_sdk_install_is_public_and_authenticated_sdk_api_call_works(self):
        import software_sdk  # noqa: F401

        guide = (ROOT_DIR / "SDK_INTEGRATION_GUIDE.md").read_text(encoding="utf-8")
        self.assertIn("Installing the SDK is public", guide)
        self.assertIn("does not require signing in", guide)

        from Software.app import app as software_app

        sdk_client = TestClient(software_app)
        unauthorized = sdk_client.post(
            "/api/sdk/workflows/start",
            json={"project_name": "sdk", "workflow_name": "public install"},
        )
        self.assertEqual(unauthorized.status_code, 401)

        authorized = sdk_client.post(
            "/api/sdk/workflows/start",
            headers={"X-Software-API-Key": "dev-key"},
            json={"project_name": "sdk", "workflow_name": "protected call"},
        )
        self.assertEqual(authorized.status_code, 200, authorized.text)
        self.assertTrue(authorized.json()["workflow_id"])


if __name__ == "__main__":
    unittest.main()
