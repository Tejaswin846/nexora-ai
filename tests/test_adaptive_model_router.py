import unittest
import sys
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "backend"))
sys.path.insert(0, str(ROOT_DIR))

from backend import main as runtime


class AdaptiveModelRouterTests(unittest.TestCase):
    def test_general_frontend_mode_allows_backend_auto_routing(self):
        frontend = (ROOT_DIR / "frontend" / "index.html").read_text(encoding="utf-8")
        start = frontend.index("function getBackendModeForRequest()")
        router_source = frontend[start : start + 700]
        self.assertIn('return "auto";', router_source)

    def test_adaptive_mode_disables_legacy_force_ollama_setting(self):
        with (
            patch.object(runtime, "ADAPTIVE_MODEL_ROUTING", True),
            patch.object(runtime, "QWEN_LOCK_ENABLED", False),
            patch.dict("os.environ", {"NEXORA_FORCE_OLLAMA_CHAT": "true"}),
        ):
            self.assertFalse(runtime.force_ollama_chat_enabled())

    def test_instant_requests_prioritize_low_latency_provider(self):
        with patch.object(
            runtime,
            "configured_free_providers",
            return_value=["gemini", "groq", "pollinations"],
        ):
            self.assertEqual(
                runtime.provider_order_for_request(None, "instant"),
                ["groq", "gemini", "pollinations"],
            )

    def test_thinking_requests_prioritize_reasoning_provider(self):
        with patch.object(
            runtime,
            "configured_free_providers",
            return_value=["groq", "openrouter", "gemini", "pollinations"],
        ):
            self.assertEqual(
                runtime.provider_order_for_request(None, "thinking"),
                ["gemini", "openrouter", "groq", "pollinations"],
            )

    def test_ollama_selects_different_fast_and_thinking_models(self):
        available = ["qwen2.5:3b", "qwen3:14b"]
        with patch.object(runtime, "system_profile", return_value={"level": "balanced"}):
            self.assertEqual(runtime.select_ollama_model(None, "instant", available), "qwen2.5:3b")
            self.assertEqual(runtime.select_ollama_model(None, "thinking", available), "qwen3:14b")

    def test_online_provider_is_tried_without_slow_ollama_probe(self):
        with (
            patch.object(runtime, "configured_free_providers", return_value=["groq"]),
            patch.object(runtime, "free_api_chat", return_value=("fast answer", "groq:test:instant")),
            patch.object(runtime, "ollama_available_models") as ollama_models,
            patch.object(runtime, "FREE_API_PROVIDER", "auto"),
            patch.object(runtime, "OLLAMA_MODE", "fallback"),
        ):
            reply, model, tools = runtime.generate_with_engine_club(
                [{"role": "user", "content": "hello"}],
                None,
                "instant",
                "chat",
                "short",
                False,
                "",
                "",
                "",
            )

        self.assertEqual(reply, "fast answer")
        self.assertEqual(model, "groq:test:instant")
        self.assertIn("adaptive_route:instant:groq", tools)
        ollama_models.assert_not_called()

    def test_ollama_is_used_after_online_providers_fail(self):
        with (
            patch.object(runtime, "configured_free_providers", return_value=["groq"]),
            patch.object(runtime, "free_api_chat", side_effect=RuntimeError("provider unavailable")),
            patch.object(runtime, "ollama_available_models", return_value=["qwen2.5:3b"]),
            patch.object(runtime, "ollama_chat", return_value="local fallback"),
            patch.object(runtime, "FREE_API_PROVIDER", "auto"),
            patch.object(runtime, "OLLAMA_MODE", "fallback"),
            patch.object(runtime, "system_profile", return_value={"level": "balanced"}),
        ):
            reply, model, tools = runtime.generate_with_engine_club(
                [{"role": "user", "content": "hello"}],
                None,
                "instant",
                "chat",
                "short",
                False,
                "",
                "",
                "",
            )

        self.assertEqual(reply, "local fallback")
        self.assertEqual(model, "ollama:qwen2.5:3b:instant")
        self.assertIn("free_api_failed", tools)


if __name__ == "__main__":
    unittest.main()
