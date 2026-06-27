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


class ExternalAITesterModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(cls.temp_dir.name)
        os.environ["SOFTWARE_API_DB_PATH"] = str(temp_path / "software_reliability.db")
        os.environ["RELIABILITY_DB_PATH"] = str(temp_path / "reliability.db")
        cls.app_module = importlib.import_module("Software.app")
        cls.app_module.DATA_DIR = temp_path
        cls.app_module.DB_PATH = temp_path / "software_reliability.db"
        cls.client = TestClient(cls.app_module.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_scenarios_endpoint_exposes_required_categories_and_sandbox(self):
        response = self.client.get("/api/external-test/scenarios")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        categories = [scenario["category"] for scenario in payload["scenarios"]]

        self.assertEqual(len(payload["scenarios"]), 12)
        self.assertIn("Memory test", categories)
        self.assertIn("Prompt injection resistance test", categories)
        self.assertIn("Recovery/self-fix suggestion test", categories)
        self.assertTrue(payload["sandbox_mode"]["enabled"])
        self.assertIn("No real emails sent", payload["sandbox_mode"]["limits"])
        self.assertIn(
            "You are testing this AI workflow software. Use the provided URL.",
            payload["copy_prompt"],
        )

    def test_run_endpoint_creates_dry_run_results_and_public_report(self):
        response = self.client.post(
            "/api/external-test/run",
            json={
                "tester_name": "ChatGPT",
                "tester_model": "external-ai",
                "public_url": "https://public.example",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total_categories"], 12)
        self.assertEqual(payload["failed_categories"], 0)
        self.assertEqual(payload["safety_score"], 100.0)
        self.assertEqual(payload["reliability_score"], 100.0)
        self.assertEqual(payload["tool_use_score"], 100.0)
        self.assertEqual(payload["verdict"], "External AI Ready")

        gmail_result = next(
            result for result in payload["scenario_results"] if result["scenario_id"] == "gmail_dry_run"
        )
        self.assertIn("gmail.send", gmail_result["blocked_unsafe_actions"])
        self.assertEqual(gmail_result["confirmation_cards"][0]["status"], "blocked")

        results_response = self.client.get(payload["results_url"])
        self.assertEqual(results_response.status_code, 200)
        results_payload = results_response.json()
        self.assertIn("gmail.send", results_payload["blocked_unsafe_actions"])
        self.assertIn("No real calendar events created", results_payload["sandbox_policy"]["limits"])

        report_response = self.client.get(payload["report_url"])
        self.assertEqual(report_response.status_code, 200)
        self.assertIn("External AI Test Report", report_response.text)
        self.assertIn("Blocked Unsafe Actions", report_response.text)
        self.assertIn("Final verdict", report_response.text)

    def test_observed_failure_lowers_scores_and_is_reported(self):
        response = self.client.post(
            "/api/external-test/run",
            json={
                "tester_name": "Claude",
                "tester_model": "external-ai",
                "public_url": "https://public.example",
                "scenario_ids": ["gmail_dry_run"],
                "observations": [
                    {
                        "scenario_id": "gmail_dry_run",
                        "passed": False,
                        "system_response": "The software attempted a live send.",
                        "failures": ["Send action was not blocked"],
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total_categories"], 1)
        self.assertEqual(payload["failed_categories"], 1)
        self.assertEqual(payload["safety_score"], 0.0)
        self.assertLess(payload["final_score"], 100.0)
        self.assertEqual(payload["verdict"], "Not ready: sandbox safety failed")

        results_response = self.client.get(payload["results_url"])
        self.assertEqual(results_response.status_code, 200)
        results_payload = results_response.json()
        self.assertIn("Send action was not blocked", results_payload["failures"])
        self.assertEqual(results_payload["scenario_results"][0]["system_response"], "The software attempted a live send.")


if __name__ == "__main__":
    unittest.main()
