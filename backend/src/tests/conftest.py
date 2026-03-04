import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Ensure src package is on sys.path
# Only add SRC_DIR - do NOT add BACKEND_ROOT to avoid package collision
HERE = os.path.dirname(__file__)
SRC_DIR = os.path.abspath(os.path.join(HERE, ".."))

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


# ============== LLM Mock Fixtures ==============

@pytest.fixture
def mock_ollama_response():
    """
    Fixture to mock BaseAgent.call_ollama with a custom response.
    Usage:
        def test_something(mock_ollama_response):
            mock_ollama_response.return_value = '{"logic_type": "CONTAINS", "target": "1"}'
    """
    with patch('core.agents.BaseAgent.call_ollama') as mock:
        yield mock


@pytest.fixture
def mock_repair_ollama():
    """
    Fixture to mock DFARepairEngine._call_ollama with a custom response.
    Usage:
        def test_repair(mock_repair_ollama):
            mock_repair_ollama.return_value = '{"states": ["q0"], ...}'
    """
    with patch('core.repair.DFARepairEngine._call_ollama') as mock:
        yield mock


@pytest.fixture
def valid_dfa_json():
    """Returns a valid DFA JSON response string for mocking."""
    return '''{
        "states": ["q0", "q1"],
        "alphabet": ["0", "1"],
        "start_state": "q0",
        "accept_states": ["q1"],
        "transitions": {
            "q0": {"0": "q0", "1": "q1"},
            "q1": {"0": "q0", "1": "q1"}
        }
    }'''


@pytest.fixture
def truncated_dfa_json():
    """Returns a truncated/invalid DFA JSON for testing retry logic."""
    return '{"states": ["q0"'  # Missing closing brackets


@pytest.fixture
def mock_requests_post():
    """
    Fixture to mock requests.post for repair engine testing.
    Usage:
        def test_repair_with_requests(mock_requests_post):
            mock_requests_post.return_value.status_code = 200
            mock_requests_post.return_value.json.return_value = {"response": "..."}
    """
    with patch('requests.post') as mock:
        yield mock
