"""
Auto-DFA API Tests

Comprehensive tests for the FastAPI endpoints including:
- Input validation and sanitization
- Error responses for edge cases
- Health endpoint
- Auth enforcement
"""

import sys
import pytest
from unittest.mock import MagicMock, patch

# We need to mock DFAGeneratorSystem before importing app
# to avoid requiring Ollama at test time.
# api.py does "from main import DFAGeneratorSystem", so we pre-populate
# sys.modules with mocks before api.py tries to import them.

# Pre-create a mock for `main` module before api.py tries to import it
mock_main = MagicMock()
mock_system_instance = MagicMock()
mock_main.DFAGeneratorSystem.return_value = mock_system_instance
sys.modules["main"] = mock_main

# Also mock core.repair to avoid import errors
mock_repair = MagicMock()
mock_repair.LLMConnectionError = type("LLMConnectionError", (Exception,), {})
sys.modules["core"] = MagicMock()
sys.modules["core.repair"] = mock_repair

from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "system_initialized" in data
        assert "version" in data

    def test_root_returns_api_info(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Auto-DFA API"
        assert "/generate" in data["endpoints"]


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_empty_prompt_returns_422(self):
        """Empty string should fail Pydantic validation."""
        response = client.post("/generate", json={"prompt": ""})
        assert response.status_code == 422

    def test_whitespace_only_prompt_returns_422(self):
        """Whitespace-only string should fail after stripping."""
        response = client.post("/generate", json={"prompt": "   "})
        assert response.status_code == 422

    def test_missing_prompt_field_returns_422(self):
        """Missing 'prompt' field should fail validation."""
        response = client.post("/generate", json={"query": "ends with a"})
        assert response.status_code == 422

    def test_overly_long_prompt_returns_422(self):
        """Prompt exceeding 500 chars should be rejected."""
        long_prompt = "a" * 501
        response = client.post("/generate", json={"prompt": long_prompt})
        assert response.status_code == 422

    def test_prompt_at_max_length_accepted(self):
        """Prompt at exactly 500 chars should pass validation (may fail downstream)."""
        prompt = "a" * 500
        # Mock the system to avoid LLM calls
        mock_analyst = MagicMock()
        mock_spec = MagicMock()
        mock_spec.logic_type = "STARTS_WITH"
        mock_spec.target = "a"
        mock_spec.model_dump.return_value = {"logic_type": "STARTS_WITH", "target": "a"}
        mock_analyst.analyze.return_value = mock_spec

        mock_architect = MagicMock()
        mock_dfa = MagicMock()
        mock_dfa.states = ["q0", "q1"]
        mock_dfa.model_dump.return_value = {"states": ["q0", "q1"]}
        mock_architect.design.return_value = mock_dfa

        mock_validator = MagicMock()
        mock_validator.validate.return_value = (True, None)

        app.state.system.analyst = mock_analyst
        app.state.system.architect = mock_architect
        app.state.system.validator = mock_validator

        response = client.post("/generate", json={"prompt": prompt})
        # Should pass input validation (status != 422)
        assert response.status_code != 422

    def test_control_characters_stripped(self):
        """Control characters in prompt should be stripped, not cause errors."""
        prompt = "ends with \x00\x01a"
        mock_analyst = MagicMock()
        mock_spec = MagicMock()
        mock_spec.logic_type = "ENDS_WITH"
        mock_spec.target = "a"
        mock_spec.model_dump.return_value = {"logic_type": "ENDS_WITH", "target": "a"}
        mock_analyst.analyze.return_value = mock_spec

        mock_architect = MagicMock()
        mock_dfa = MagicMock()
        mock_dfa.states = ["q0", "q1"]
        mock_dfa.model_dump.return_value = {"states": ["q0", "q1"]}
        mock_architect.design.return_value = mock_dfa

        mock_validator = MagicMock()
        mock_validator.validate.return_value = (True, None)

        app.state.system.analyst = mock_analyst
        app.state.system.architect = mock_architect
        app.state.system.validator = mock_validator

        response = client.post("/generate", json={"prompt": prompt})
        assert response.status_code != 422
        # Verify the sanitized prompt was passed (without control chars)
        call_args = mock_analyst.analyze.call_args[0][0]
        assert "\x00" not in call_args
        assert "\x01" not in call_args


# ---------------------------------------------------------------------------
# Generate endpoint — success path
# ---------------------------------------------------------------------------

class TestGenerateEndpoint:
    def setup_method(self):
        """Set up mocks for a successful generation."""
        self.mock_spec = MagicMock()
        self.mock_spec.logic_type = "ENDS_WITH"
        self.mock_spec.target = "a"
        self.mock_spec.model_dump.return_value = {
            "logic_type": "ENDS_WITH",
            "target": "a",
            "alphabet": ["a", "b"]
        }

        self.mock_dfa = MagicMock()
        self.mock_dfa.states = ["q0", "q1"]
        self.mock_dfa.model_dump.return_value = {
            "states": ["q0", "q1"],
            "alphabet": ["a", "b"],
            "start_state": "q0",
            "accept_states": ["q1"],
            "transitions": {"q0": {"a": "q1", "b": "q0"}, "q1": {"a": "q1", "b": "q0"}}
        }

        app.state.system.analyst.analyze.return_value = self.mock_spec
        app.state.system.architect.design.return_value = self.mock_dfa
        app.state.system.validator.validate.return_value = (True, None)

    def test_successful_generation(self):
        response = client.post("/generate", json={"prompt": "ends with a"})
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "dfa" in data
        assert "spec" in data
        assert "performance" in data
        assert "total_ms" in data["performance"]

    def test_response_includes_timing(self):
        response = client.post("/generate", json={"prompt": "ends with a"})
        data = response.json()
        perf = data["performance"]
        assert "analysis_ms" in perf
        assert "architecture_ms" in perf
        assert "validation_ms" in perf
        assert all(isinstance(v, (int, float)) for v in perf.values())


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------

class TestAuthentication:
    def test_no_auth_when_api_key_not_set(self):
        """When API_KEY env var is not set, auth should be disabled."""
        with patch("api.API_KEY", None):
            response = client.post("/generate", json={"prompt": "ends with a"})
            assert response.status_code != 401

    def test_auth_required_when_api_key_set(self):
        """When API_KEY is set, missing header should return 401."""
        with patch("api.API_KEY", "test-secret-key"):
            response = client.post("/generate", json={"prompt": "ends with a"})
            assert response.status_code == 401

    def test_valid_api_key_accepted(self):
        """Correct API key should allow the request through."""
        with patch("api.API_KEY", "test-secret-key"):
            response = client.post(
                "/generate",
                json={"prompt": "ends with a"},
                headers={"X-API-Key": "test-secret-key"}
            )
            assert response.status_code != 401

    def test_invalid_api_key_rejected(self):
        """Wrong API key should return 401."""
        with patch("api.API_KEY", "test-secret-key"):
            response = client.post(
                "/generate",
                json={"prompt": "ends with a"},
                headers={"X-API-Key": "wrong-key"}
            )
            assert response.status_code == 401
