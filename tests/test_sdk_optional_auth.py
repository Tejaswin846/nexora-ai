from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

AUTH_REQUIRED_MESSAGE = (
    "Authentication required for this cloud feature. You can still install and use the SDK locally without signing in."
)


class FakeSupabaseStorageClient:
    configured = True

    def upsert_user_profile(self, profile):
        return {"ok": True, "profile": profile}


class FakeClerkVerifier:
    configured = True

    def __init__(self, app_module):
        self.app_module = app_module

    def verify_token(self, token: str):
        if token != "clerk-token":
            raise self.app_module.ClerkAuthError("Invalid or expired Clerk session token.", status_code=401)
        return self.app_module.ClerkUserContext(
            user_id="user_clerk",
            email="clerk@example.com",
            name="Clerk User",
            session_id="sess_clerk",
            claims={"sub": "user_clerk", "email": "clerk@example.com"},
        )


class SDKOptionalAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(cls.temp_dir.name)
        os.environ["SOFTWARE_API_DB_PATH"] = str(temp_path / "software_reliability.db")
        os.environ["RELIABILITY_DB_PATH"] = str(temp_path / "reliability.db")
        cls.app_module = importlib.import_module("Software.app")
        cls.app_module.DATA_DIR = temp_path
        cls.app_module.DB_PATH = temp_path / "software_reliability.db"
        cls.app_module.clerk_verifier = FakeClerkVerifier(cls.app_module)
        cls.app_module.supabase_storage_client = FakeSupabaseStorageClient()
        cls.client = TestClient(cls.app_module.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_sdk_docs_visible_without_login(self):
        response = self.client.get("/sdk")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Install Without Login", response.text)
        self.assertIn("Public Local Mode", response.text)
        self.assertIn("Authenticated Cloud Mode", response.text)
        self.assertIn("software login", response.text)

    def test_sdk_install_commands_visible_without_login(self):
        page = self.client.get("/sdk")
        docs = self.client.get("/api/sdk/docs")

        self.assertEqual(page.status_code, 200)
        self.assertIn("pip install software-sdk", page.text)
        self.assertIn("npm install software-sdk", page.text)
        self.assertEqual(docs.status_code, 200)
        payload = docs.json()
        self.assertFalse(payload["auth_required_for_install"])
        self.assertEqual(payload["install"]["python"], "pip install software-sdk")
        self.assertEqual(payload["install"]["npm"], "npm install software-sdk")

    def test_local_sdk_mode_works_without_auth(self):
        from software_sdk import ReliabilityMonitor

        sdk = ReliabilityMonitor(project_name="local-agent")
        plan = sdk.create_local_plan("Check a workflow")
        validation = sdk.validate_local_workflow(plan)
        dry_run = sdk.dry_run_workflow("sandbox validation", plan["steps"])
        sandbox = sdk.test_sandbox_workflow()

        self.assertEqual(sdk.mode, "local")
        self.assertTrue(plan["ok"])
        self.assertTrue(validation["ok"])
        self.assertTrue(dry_run["ok"])
        self.assertFalse(dry_run["requires_auth"])
        self.assertEqual(dry_run["side_effects"], "none")
        self.assertTrue(sandbox["ok"])

    def test_protected_cloud_api_rejects_unauthenticated_requests_clearly(self):
        response = self.client.post(
            "/api/sdk/workflows/start",
            json={"project_name": "sdk", "workflow_name": "protected cloud"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], AUTH_REQUIRED_MESSAGE)

    def test_dashboard_is_protected_but_sdk_page_is_public(self):
        dashboard = self.client.get("/dashboard")
        api_dashboard = self.client.get("/api/dashboard")
        sdk_page = self.client.get("/sdk")

        self.assertEqual(dashboard.status_code, 401)
        self.assertEqual(api_dashboard.status_code, 401)
        self.assertEqual(sdk_page.status_code, 200)

    def test_authenticated_api_key_works(self):
        response = self.client.post(
            "/api/sdk/workflows/start",
            headers={"X-Software-API-Key": "dev-key"},
            json={"project_name": "sdk", "workflow_name": "protected cloud"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["workflow_id"])

    def test_authenticated_clerk_jwt_works_for_cloud_api(self):
        response = self.client.post(
            "/api/sdk/workflows/start",
            headers={"Authorization": "Bearer clerk-token"},
            json={"project_name": "sdk", "workflow_name": "protected cloud"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["workflow_id"])


if __name__ == "__main__":
    unittest.main()
