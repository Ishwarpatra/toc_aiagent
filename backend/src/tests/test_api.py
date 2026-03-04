"""
Auto-DFA API Tests

Comprehensive tests for the FastAPI endpoints including:
- Input validation and sanitization
- Error responses for edge cases
- Health endpoint
- Auth enforcement
"""

import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from api import app


# ---------------------------------------------------------------------------
# Fixtures - Mock system for API endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_system():
    """Create a fully mocked DFAGeneratorSystem for API tests."""
    system = MagicMock()
    
    # Mock spec
    mock_spec = MagicMock()
    mock_spec.logic_type = "ENDS_WITH"
    mock_spec.target = "a"
    mock_spec.model_dump.return_value = {
        "logic_type": "ENDS_WITH",
        "target": "a",
        "alphabet": ["a", "b"]
    }
    
    # Mock DFA
    mock_dfa = MagicMock()
    mock_dfa.states = ["q0", "q1"]
    mock_dfa.model_dump.return_value = {
        "states": ["q0", "q1"],
        "alphabet": ["a", "b"],
        "start_state": "q0",
        "accept_states": ["q1"],
        "transitions": {"q0": {"a": "q1", "b": "q0"}, "q1": {"a": "q1", "b": "q0"}}
    }
    
    # Set up analyst mock
    system.analyst.analyze.return_value = mock_spec
    
    # Set up architect mock
    system.architect.design.return_value = mock_dfa
    
    # Set up validator mock
    system.validator.validate.return_value = (True, None)
    
    return system


@pytest.fixture
def client(mock_system):
    """Create test client with mocked system injected into app.state."""
    # Inject mock system into app.state
    app.state.system = mock_system
    
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "system_initialized" in data
        assert "version" in data

    def test_root_returns_api_info(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Auto-DFA API"
        assert "/generate" in data["endpoints"]


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_empty_prompt_returns_422(self, client):
        """Empty string should fail Pydantic validation."""
        response = client.post("/generate", json={"prompt": ""})
        assert response.status_code == 422

    def test_whitespace_only_prompt_returns_422(self, client):
        """Whitespace-only string should fail after stripping."""
        response = client.post("/generate", json={"prompt": "   "})
        assert response.status_code == 422

    def test_missing_prompt_field_returns_422(self, client):
        """Missing 'prompt' field should fail validation."""
        response = client.post("/generate", json={"query": "ends with a"})
        assert response.status_code == 422

    def test_overly_long_prompt_returns_422(self, client):
        """Prompt exceeding 500 chars should be rejected."""
        long_prompt = "a" * 501
        response = client.post("/generate", json={"prompt": long_prompt})
        assert response.status_code == 422

    def test_prompt_at_max_length_accepted(self, client):
        """Prompt at exactly 500 chars should pass validation (may fail downstream)."""
        prompt = "a" * 500
        response = client.post("/generate", json={"prompt": prompt})
        # Should pass input validation (status != 422)
        assert response.status_code != 422

    def test_control_characters_stripped(self, client):
        """Control characters in prompt should be stripped, not cause errors."""
        prompt = "ends with \x00\x01a"
        response = client.post("/generate", json={"prompt": prompt})
        # Should pass input validation (may fail downstream, but not 422)
        assert response.status_code != 422


# ---------------------------------------------------------------------------
# Generate endpoint — success path
# ---------------------------------------------------------------------------

class TestGenerateEndpoint:
    def test_successful_generation(self, client):
        response = client.post("/generate", json={"prompt": "ends with a"})
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "dfa" in data
        assert "spec" in data
        assert "performance" in data
        assert "total_ms" in data["performance"]

    def test_response_includes_timing(self, client):
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
    def test_no_auth_when_api_key_not_set(self, client):
        """When API_KEY env var is not set, auth should be disabled."""
        with patch("api.API_KEY", None):
            response = client.post("/generate", json={"prompt": "ends with a"})
            assert response.status_code != 401

    def test_auth_required_when_api_key_set(self, client):
        """When API_KEY is set, requests without key should be rejected."""
        with patch("api.API_KEY", "test-secret-key"):
            response = client.post("/generate", json={"prompt": "ends with a"})
            assert response.status_code == 401

    def test_valid_api_key_accepted(self, client):
        """Valid API key should be accepted."""
        with patch("api.API_KEY", "test-secret-key"):
            response = client.post(
                "/generate",
                json={"prompt": "ends with a"},
                headers={"X-API-Key": "test-secret-key"}
            )
            assert response.status_code == 200

    def test_invalid_api_key_rejected(self, client):
        """Invalid API key should be rejected."""
        with patch("api.API_KEY", "test-secret-key"):
            response = client.post(
                "/generate",
                json={"prompt": "ends with a"},
                headers={"X-API-Key": "wrong-key"}
            )
            assert response.status_code == 401
