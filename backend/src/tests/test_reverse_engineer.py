"""
Tests for Image-to-Language Reverse Engineering Pipeline:
- VisionAgent and structural validation
- DescriberAgent and description generation
- POST /reverse-engineer FastAPI endpoint
"""

import io
import json
import base64
import unittest
from unittest.mock import MagicMock, patch, PropertyMock
from fastapi.testclient import TestClient

from core.models import DFA
from core.validator import DeterministicValidator
from core.grammar import GrammarBuilder
from core.agents import VisionAgent, DescriberAgent
from core.providers import VisionProvider
from api import app


class MockProvider(VisionProvider):
    """Mock vision provider for deterministic unit testing."""
    def __init__(self, return_data=None, should_fail=False):
        self.return_data = return_data or {
            "states": ["q0", "q1"],
            "alphabet": ["0", "1"],
            "transitions": {
                "q0": {"0": "q0", "1": "q1"},
                "q1": {"0": "q0", "1": "q1"}
            },
            "start_state": "q0",
            "accept_states": ["q1"]
        }
        self.should_fail = should_fail

    def get_models(self):
        return ["mock-vision-model"]

    def call(self, model, system_prompt, user_text, image_b64):
        if self.should_fail:
            raise RuntimeError("Mock provider simulated API failure")
        return self.return_data

    def is_rate_limit_daily(self, error):
        return False


class TestReverseEngineeringComponents(unittest.TestCase):
    def test_deterministic_validator_structure(self):
        # Valid DFA
        valid_dfa = DFA(
            states={"q0", "q1"},
            alphabet={"0", "1"},
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            start_state="q0",
            accept_states={"q1"}
        )
        ok, msg = DeterministicValidator.validate_structure(valid_dfa)
        self.assertTrue(ok)
        self.assertEqual(msg, "Valid DFA structure")

        # Case 1: Unknown target state
        dfa_bad_target = DFA(
            states={"q0", "q1"},
            alphabet={"0", "1"},
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            start_state="q0",
            accept_states={"q1"}
        )
        dfa_bad_target.transitions["q0"]["0"] = "unregistered_state"
        ok, msg = DeterministicValidator.validate_structure(dfa_bad_target)
        self.assertFalse(ok)
        self.assertIn("target state", msg)

        # Case 2: Transition symbol not in alphabet
        dfa_bad_symbol = DFA(
            states={"q0", "q1"},
            alphabet={"0", "1"},
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            start_state="q0",
            accept_states={"q1"}
        )
        dfa_bad_symbol.transitions["q0"]["x"] = "q1"
        ok, msg = DeterministicValidator.validate_structure(dfa_bad_symbol)
        self.assertFalse(ok)
        self.assertIn("symbol", msg)

    def test_vision_agent_success(self):
        mock_prov = MockProvider()
        agent = VisionAgent(providers=[mock_prov])
        fake_b64 = base64.b64encode(b"fake_image_bytes").decode("utf-8")

        dfa = agent.process_image(fake_b64)
        self.assertIsInstance(dfa, DFA)
        self.assertEqual(dfa.start_state, "q0")
        self.assertEqual(dfa.accept_states, ["q1"])

    def test_vision_agent_invalid_graph_rejection(self):
        # Provider returns malformed graph (transition to unknown state)
        bad_data = {
            "states": ["q0"],
            "alphabet": ["0"],
            "transitions": {"q0": {"0": "ghost_state"}},
            "start_state": "q0",
            "accept_states": []
        }
        mock_prov = MockProvider(return_data=bad_data)
        agent = VisionAgent(providers=[mock_prov])

        with self.assertRaises(ValueError) as ctx:
            agent.process_image("fake_b64")
        self.assertIn("structural validation failed", str(ctx.exception))

    def test_vision_agent_all_providers_fail(self):
        mock_prov = MockProvider(should_fail=True)
        agent = VisionAgent(providers=[mock_prov])
        with self.assertRaises(ValueError) as ctx:
            agent.process_image("fake_b64")
        self.assertIn("Vision processing failed", str(ctx.exception))

    def test_describer_agent_with_provider(self):
        mock_prov = MockProvider(return_data={"description": "Accepts binary strings ending with 1."})
        agent = DescriberAgent(providers=[mock_prov])
        dfa = DFA(
            states={"q0", "q1"},
            alphabet={"0", "1"},
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            start_state="q0",
            accept_states={"q1"}
        )
        grammar = GrammarBuilder.build_from_dfa(dfa)
        desc = agent.describe(dfa, grammar)
        self.assertEqual(desc, "Accepts binary strings ending with 1.")

    def test_describer_agent_heuristic_fallback(self):
        # Empty providers -> heuristic description
        agent = DescriberAgent(providers=[])
        dfa = DFA(
            states={"q0", "q1"},
            alphabet={"0", "1"},
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            start_state="q0",
            accept_states={"q1"}
        )
        grammar = GrammarBuilder.build_from_dfa(dfa)
        desc = agent.describe(dfa, grammar)
        self.assertIn("regular language", desc.lower())


class TestReverseEngineerEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("api.VisionAgent")
    @patch("api.DescriberAgent")
    def test_reverse_engineer_endpoint_success(self, mock_desc_cls, mock_vision_cls):
        # Mock VisionAgent
        mock_vision_inst = MagicMock()
        mock_vision_inst.process_image.return_value = DFA(
            states={"q0", "q1"},
            alphabet={"0", "1"},
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}},
            start_state="q0",
            accept_states={"q1"}
        )
        mock_vision_cls.return_value = mock_vision_inst

        # Mock DescriberAgent
        mock_desc_inst = MagicMock()
        mock_desc_inst.describe.return_value = "Accepts strings ending in 1."
        mock_desc_cls.return_value = mock_desc_inst

        fake_image_file = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRfake_png_data")
        response = self.client.post(
            "/reverse-engineer",
            files={"file": ("diagram.png", fake_image_file, "image/png")}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["valid"])
        self.assertIn("dfa", data)
        self.assertIn("grammar", data)
        self.assertIn("grammar_formatted", data)
        self.assertEqual(data["description"], "Accepts strings ending in 1.")

    def test_reverse_engineer_invalid_file_type(self):
        text_file = io.BytesIO(b"Hello world")
        response = self.client.post(
            "/reverse-engineer",
            files={"file": ("test.txt", text_file, "text/plain")}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported image type", response.json()["detail"]["error"])

    def test_reverse_engineer_empty_file(self):
        empty_file = io.BytesIO(b"")
        response = self.client.post(
            "/reverse-engineer",
            files={"file": ("empty.png", empty_file, "image/png")}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.json()["detail"]["error"].lower())


class TestProviders(unittest.TestCase):
    def test_gemini_provider(self):
        mock_google = MagicMock()
        mock_genai = MagicMock()
        mock_google.generativeai = mock_genai
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '```json\n{"states": ["q0"], "alphabet": ["0"], "transitions": {"q0": {"0": "q0"}}, "start_state": "q0", "accept_states": ["q0"]}\n```'
        mock_instance.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_instance

        with patch.dict("sys.modules", {"google": mock_google, "google.generativeai": mock_genai}):
            from core.providers import GeminiProvider
            prov = GeminiProvider("fake_key")
            models = prov.get_models()
            self.assertIn("models/gemini-2.0-flash", models)
            self.assertTrue(prov.is_rate_limit_daily(Exception("429 ResourceExhausted: quota exceeded")))
            self.assertFalse(prov.is_rate_limit_daily(Exception("500 Internal error")))

            res = prov.call("models/gemini-2.0-flash", "sys prompt", "user text", "AAAA")
            self.assertEqual(res["start_state"], "q0")

    def test_openrouter_provider(self):
        mock_openai_module = MagicMock()
        mock_openai_cls = MagicMock()
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_openai_module.OpenAI = mock_openai_cls

        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = '{"states": ["q0"], "alphabet": ["0"], "transitions": {"q0": {"0": "q0"}}, "start_state": "q0", "accept_states": []}'
        mock_completion.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_completion

        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            from core.providers import OpenRouterProvider
            prov = OpenRouterProvider("fake_key")
            models = prov.get_models()
            self.assertIn("openai/gpt-4o", models)
            self.assertTrue(prov.is_rate_limit_daily(Exception("429 rate limit reached")))
            self.assertTrue(prov.is_rate_limit_daily(Exception("402 insufficient funds")))
            self.assertFalse(prov.is_rate_limit_daily(Exception("500 server error")))

            res = prov.call("openai/gpt-4o", "sys", "user", "AAAA")
            self.assertEqual(res["start_state"], "q0")


if __name__ == "__main__":
    unittest.main()
