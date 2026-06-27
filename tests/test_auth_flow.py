from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict

from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "backend"))
sys.path.insert(0, str(ROOT_DIR))


class FakeSupabaseStorageClient:
    configured = True

    def __init__(self) -> None:
        self.profiles: Dict[str, Dict[str, Any]] = {}

    def upsert_user_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        self.profiles[str(profile["id"])] = dict(profile)
        return {"ok": True, "profile": dict(profile)}


class FakeClerkVerifier:
    configured = True

    def __init__(self, main: Any) -> None:
        self.main = main
        self.users = {
            "alice-token": main.ClerkUserContext(
                user_id="user_alice",
                email="alice@example.com",
                name="Alice",
                session_id="sess_alice",
                claims={"sub": "user_alice", "email": "alice@example.com", "email_verified": True},
            ),
            "bob-token": main.ClerkUserContext(
                user_id="user_bob",
                email="bob@example.com",
                name="Bob",
                session_id="sess_bob",
                claims={"sub": "user_bob", "email": "bob@example.com", "email_verified": True},
            ),
        }

    def public_config(self) -> Dict[str, Any]:
        return {
            "provider": "clerk",
            "configured": True,
            "clerk_publishable_key": "pk_test_unit",
            "clerk_jwt_issuer": "https://unit-test.clerk.accounts.dev",
        }

    def verify_token(self, token: str):
        if token not in self.users:
            raise self.main.ClerkAuthError("Invalid or expired Clerk session token.", status_code=401)
        return self.users[token]


class ClerkAuthFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["NEXORA_DATA_DIR"] = cls.temp_dir.name
        os.environ["CLERK_PUBLISHABLE_KEY"] = "pk_test_unit"
        os.environ["CLERK_SECRET_KEY"] = "sk_test_unit"
        os.environ["CLERK_JWT_ISSUER"] = "https://unit-test.clerk.accounts.dev"
        os.environ["CLERK_WEBHOOK_SECRET"] = "whsec_unit"
        os.environ["SUPABASE_URL"] = "https://unit-test.supabase.co"
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "service-role-test-key"
        os.environ["NEXORA_PUBLIC_APP_URL"] = "https://nexora.test"
        os.environ["NEXORA_CACHE_FRONTEND_HTML"] = "false"
        spec = importlib.util.spec_from_file_location("nexora_backend_main_for_clerk_tests", ROOT_DIR / "backend" / "main.py")
        assert spec and spec.loader
        cls.main = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.main
        spec.loader.exec_module(cls.main)
        cls.fake_storage = FakeSupabaseStorageClient()
        cls.fake_clerk = FakeClerkVerifier(cls.main)
        cls.main.supabase_storage_client = cls.fake_storage
        cls.main.clerk_verifier = cls.fake_clerk
        cls.client = TestClient(cls.main.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def setUp(self) -> None:
        self.fake_storage.profiles.clear()
        for path in [
            self.main.USERS_FILE,
            self.main.PROJECTS_FILE,
            self.main.WORKFLOWS_FILE,
            self.main.MEMORY_FILE,
            self.main.SESSIONS_FILE,
        ]:
            path.unlink(missing_ok=True)

    def auth_headers(self, token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def test_clerk_config_and_frontend_flows_are_public(self):
        response = self.client.get("/auth/config")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["provider"], "clerk")
        self.assertEqual(payload["clerk_publishable_key"], "pk_test_unit")
        self.assertIn("google", payload["oauth_providers"])
        self.assertIn("github", payload["oauth_providers"])

        auth_js = (ROOT_DIR / "frontend" / "auth.js").read_text(encoding="utf-8")
        reset_page = (ROOT_DIR / "frontend" / "reset-password.html").read_text(encoding="utf-8")
        self.assertIn("openSignUp", auth_js)
        self.assertIn("openSignIn", auth_js)
        self.assertIn("Clerk", reset_page)
        self.assertNotIn("supabase", auth_js.lower())
        self.assertNotIn("supabase", reset_page.lower())

    def test_signup_login_and_password_reset_are_clerk_handled(self):
        signup = self.client.post(
            "/auth/signup",
            json={"name": "Alice", "email": "alice@example.com", "password": "password123"},
        )
        self.assertEqual(signup.status_code, 200)
        self.assertIn("Clerk", signup.json()["message"])

        login = self.client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "password123"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("Clerk", login.json()["message"])

        forgot = self.client.post("/auth/forgot-password", json={"email": "alice@example.com"})
        self.assertEqual(forgot.status_code, 200)
        self.assertIn("Clerk", forgot.json()["message"])

        reset = self.client.post(
            "/auth/reset-password",
            json={"access_token": "clerk-reset-token", "new_password": "new-password"},
        )
        self.assertEqual(reset.status_code, 200)
        self.assertIn("Clerk", reset.json()["message"])

    def test_protected_route_blocked_without_auth(self):
        response = self.client.get("/projects")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Login required", response.text)

    def test_protected_route_works_with_clerk_jwt_and_syncs_profile(self):
        response = self.client.get("/projects", headers=self.auth_headers("alice-token"))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user_id"], "user_alice")
        self.assertIn("user_alice", self.fake_storage.profiles)

        me = self.client.get("/auth/me", headers=self.auth_headers("alice-token"))
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["id"], "user_alice")
        self.assertEqual(me.json()["user"]["auth_provider"], "clerk")

    def test_user_data_isolation_uses_clerk_user_id(self):
        alice = self.auth_headers("alice-token")
        bob = self.auth_headers("bob-token")

        create_project = self.client.post(
            "/projects/create",
            headers=alice,
            json={"name": "Alice private project", "user_id": "user_bob", "session_id": "alice_session"},
        )
        self.assertEqual(create_project.status_code, 200, create_project.text)
        self.assertEqual(create_project.json()["project"]["user_id"], "user_alice")

        bob_projects = self.client.get("/projects", headers=bob)
        self.assertEqual(bob_projects.status_code, 200)
        self.assertEqual(bob_projects.json()["projects"], [])

        anonymous_spoof = self.client.get("/projects?user_id=user_alice")
        self.assertEqual(anonymous_spoof.status_code, 401)

        create_workflow = self.client.post(
            "/workflows/create",
            headers=alice,
            json={"name": "Alice workflow", "steps": ["one"], "user_id": "user_bob"},
        )
        self.assertEqual(create_workflow.status_code, 200, create_workflow.text)

        bob_workflows = self.client.get("/workflows", headers=bob)
        self.assertEqual(bob_workflows.status_code, 200)
        self.assertEqual(bob_workflows.json()["workflows"], [])

        self.main.upsert_memory_item("Alice secret", "user_alice", "preference")
        bob_memory = self.client.get("/memory", headers=bob)
        self.assertEqual(bob_memory.status_code, 200)
        self.assertEqual(bob_memory.json()["items"], [])


if __name__ == "__main__":
    unittest.main()
