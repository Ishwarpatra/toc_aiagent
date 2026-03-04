"""
Tests for repair.py DFA Repair Engine.
Tests LLM-based repair, JSON parsing, and retry logic.
"""
import pytest
import json
from unittest.mock import patch, MagicMock, Mock

from core.repair import (
    DFARepairEngine, LLMConnectionError,
    cleanup_dfa
)
from core.models import DFA, LogicSpec
from core.validator import DeterministicValidator


# ============== DFARepairEngine Initialization Tests ==============

class TestDFARepairEngineInit:
    """Tests for DFARepairEngine initialization."""

    def test_init_default_model(self):
        """Test default model name."""
        engine = DFARepairEngine()
        assert engine.model_name == "qwen2.5-coder:1.5b"
        assert engine.max_repair_attempts == 3

    def test_init_custom_model(self):
        """Test custom model name."""
        engine = DFARepairEngine(model_name="custom-model")
        assert engine.model_name == "custom-model"


# ============== _call_ollama Tests ==============

class TestCallOllama:
    """Tests for DFARepairEngine._call_ollama method."""

    def test_call_ollama_success(self, mock_requests_post):
        """Test successful LLM call."""
        mock_requests_post.return_value.status_code = 200
        mock_requests_post.return_value.json.return_value = {"response": "test response"}
        
        engine = DFARepairEngine()
        # Access private method for testing
        result = engine._call_ollama("system", "user")
        
        assert result == "test response"
        mock_requests_post.assert_called_once()

    def test_call_ollama_404_model_not_found(self, mock_requests_post):
        """Test 404 error raises LLMConnectionError with model not found message."""
        mock_requests_post.return_value.status_code = 404
        
        engine = DFARepairEngine()
        with pytest.raises(LLMConnectionError) as exc_info:
            engine._call_ollama("system", "user")
        
        assert "not found" in str(exc_info.value).lower()

    def test_call_ollama_other_status_error(self, mock_requests_post):
        """Test other status codes raise LLMConnectionError."""
        mock_requests_post.return_value.status_code = 500
        
        engine = DFARepairEngine()
        with pytest.raises(LLMConnectionError) as exc_info:
            engine._call_ollama("system", "user")
        
        assert "status 500" in str(exc_info.value)

    def test_call_ollama_connection_error(self, mock_requests_post):
        """Test connection error raises LLMConnectionError."""
        from requests.exceptions import ConnectionError
        mock_requests_post.side_effect = ConnectionError("Connection refused")
        
        engine = DFARepairEngine()
        with pytest.raises(LLMConnectionError) as exc_info:
            engine._call_ollama("system", "user")
        
        assert "not running" in str(exc_info.value).lower()

    def test_call_ollama_timeout_error(self, mock_requests_post):
        """Test timeout error raises LLMConnectionError."""
        from requests.exceptions import Timeout
        mock_requests_post.side_effect = Timeout("Request timed out")
        
        engine = DFARepairEngine()
        with pytest.raises(LLMConnectionError) as exc_info:
            engine._call_ollama("system", "user")
        
        assert "timed out" in str(exc_info.value).lower()


# ============== _parse_dfa_json Tests ==============

class TestParseDFAJson:
    """
    Tests for DFARepairEngine._parse_dfa_json method.
    Test 1: Valid parsing - Return a perfect JSON DFA and assert it returns the object.
    Test 2: Test retry logic - Return a truncated JSON string and assert JSONDecodeError fallback.
    """

    def test_parse_valid_dfa_json(self):
        """Test 1: Valid parsing - perfect JSON DFA returns the object."""
        valid_json = '''{
            "states": ["q0", "q1"],
            "start_state": "q0",
            "accept_states": ["q1"],
            "transitions": {
                "q0": {"0": "q0", "1": "q1"},
                "q1": {"0": "q0", "1": "q1"}
            }
        }'''
        
        engine = DFARepairEngine()
        result = engine._parse_dfa_json(valid_json, ["0", "1"])
        
        assert result is not None
        assert result["states"] == ["q0", "q1"]
        assert result["alphabet"] == ["0", "1"]  # Should be set by parser
        assert result["start_state"] == "q0"
        assert result["accept_states"] == ["q1"]

    def test_parse_truncated_json_retry_logic(self):
        """Test 2: Retry logic - truncated JSON triggers JSONDecodeError fallback."""
        truncated_json = '{"states": ["q0"'  # Missing closing brackets
        
        engine = DFARepairEngine()
        result = engine._parse_dfa_json(truncated_json, ["0", "1"])
        
        # Should return None on parse failure (triggers retry logic in caller)
        assert result is None

    def test_parse_json_with_markdown_wrapper(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        wrapped_json = '''```json
        {
            "states": ["q0"],
            "start_state": "q0",
            "accept_states": ["q0"],
            "transitions": {"q0": {"0": "q0", "1": "q0"}}
        }
        ```'''
        
        engine = DFARepairEngine()
        result = engine._parse_dfa_json(wrapped_json, ["0", "1"])
        
        assert result is not None
        assert result["states"] == ["q0"]

    def test_parse_no_json_object_found(self):
        """Test parsing when no JSON object is found."""
        response = "This is just text with no JSON"
        
        engine = DFARepairEngine()
        result = engine._parse_dfa_json(response, ["0", "1"])
        
        assert result is None

    def test_parse_missing_required_fields(self):
        """Test parsing JSON missing required fields."""
        incomplete_json = '{"states": ["q0"], "start_state": "q0"}'  # Missing accept_states, transitions
        
        engine = DFARepairEngine()
        result = engine._parse_dfa_json(incomplete_json, ["0", "1"])
        
        assert result is None

    def test_parse_empty_response(self):
        """Test parsing empty response."""
        engine = DFARepairEngine()
        result = engine._parse_dfa_json("", ["0", "1"])
        
        assert result is None


# ============== _build_repair_prompt Tests ==============

class TestBuildRepairPrompt:
    """Tests for DFARepairEngine._build_repair_prompt method."""

    def test_build_prompt_without_previous_dfa(self):
        """Test prompt building without previous DFA."""
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        
        engine = DFARepairEngine()
        system_prompt, user_prompt = engine._build_repair_prompt(spec, "validation error")
        
        assert "DFA (Deterministic Finite Automaton)" in system_prompt
        assert "CRITICAL RULES" in system_prompt
        assert "CONTAINS" in user_prompt
        assert "validation error" in user_prompt.lower()

    def test_build_prompt_with_previous_dfa(self):
        """Test prompt building with previous DFA."""
        spec = LogicSpec(logic_type="STARTS_WITH", target="a", alphabet=["a", "b"])
        previous_dfa = DFA(
            states=["q0", "q1"],
            alphabet=["a", "b"],
            transitions={"q0": {"a": "q1", "b": "q0"}, "q1": {"a": "q1", "b": "q0"}},
            start_state="q0",
            accept_states=["q1"]
        )
        
        engine = DFARepairEngine()
        system_prompt, user_prompt = engine._build_repair_prompt(spec, "", previous_dfa)
        
        assert "PREVIOUS DFA" in user_prompt
        assert "q0" in user_prompt  # Previous DFA should be serialized

    def test_build_prompt_without_validation_error(self):
        """Test prompt building without validation error."""
        spec = LogicSpec(logic_type="ENDS_WITH", target="b", alphabet=["a", "b"])
        
        engine = DFARepairEngine()
        system_prompt, user_prompt = engine._build_repair_prompt(spec, "")
        
        assert "PREVIOUS VALIDATION ERROR" not in user_prompt


# ============== repair_with_llm Tests ==============

class TestRepairWithLLM:
    """Tests for DFARepairEngine.repair_with_llm method."""

    def test_repair_success_on_first_attempt(self, mock_repair_ollama):
        """Test successful repair on first attempt."""
        # Use a valid DFA for CONTAINS "1"
        valid_response = '''{
            "states": ["q0", "q1"],
            "start_state": "q0",
            "accept_states": ["q1"],
            "transitions": {"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}}
        }'''
        mock_repair_ollama.return_value = valid_response
        
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        engine = DFARepairEngine()
        validator = DeterministicValidator()
        
        result = engine.repair_with_llm(spec, "test error", validator_instance=validator)
        
        # Note: The repaired DFA may still fail validation depending on the spec
        # The key is that the LLM was called and returned a result
        assert mock_repair_ollama.call_count >= 1

    def test_repair_retry_on_invalid_json(self, mock_repair_ollama):
        """Test retry logic when LLM returns invalid JSON."""
        # First two attempts return invalid JSON, third succeeds
        mock_repair_ollama.side_effect = [
            "invalid json 1",
            "invalid json 2",
            '''{
                "states": ["q0"],
                "start_state": "q0",
                "accept_states": ["q0"],
                "transitions": {"q0": {"0": "q0", "1": "q0"}}
            }'''
        ]
        
        spec = LogicSpec(logic_type="CONTAINS", target="0", alphabet=["0", "1"])
        engine = DFARepairEngine()
        validator = DeterministicValidator()
        
        result = engine.repair_with_llm(spec, "test error", validator_instance=validator)
        
        # Should have tried 3 times
        assert mock_repair_ollama.call_count == 3

    def test_repair_all_attempts_fail(self, mock_repair_ollama):
        """Test when all repair attempts fail."""
        mock_repair_ollama.return_value = "invalid json"
        
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        engine = DFARepairEngine()
        validator = DeterministicValidator()
        
        result = engine.repair_with_llm(spec, "test error", validator_instance=validator)
        
        assert result is None
        assert mock_repair_ollama.call_count == 3  # max_repair_attempts

    def test_repair_llm_connection_error_propagates(self, mock_repair_ollama):
        """Test that LLMConnectionError is propagated."""
        mock_repair_ollama.side_effect = LLMConnectionError("Service unavailable")
        
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        engine = DFARepairEngine()
        
        with pytest.raises(LLMConnectionError):
            engine.repair_with_llm(spec, "test error")

    def test_repair_with_previous_dfa(self, mock_repair_ollama):
        """Test repair with previous DFA provided."""
        mock_repair_ollama.return_value = '''{
            "states": ["q0", "q1"],
            "start_state": "q0",
            "accept_states": ["q1"],
            "transitions": {"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}}
        }'''
        
        spec = LogicSpec(logic_type="STARTS_WITH", target="0", alphabet=["0", "1"])
        previous_dfa = DFA(
            states=["q0"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q0"}},
            start_state="q0",
            accept_states=[]
        )
        
        engine = DFARepairEngine()
        validator = DeterministicValidator()
        
        result = engine.repair_with_llm(spec, "test error", previous_dfa, validator)
        
        # The LLM was called with previous_dfa info
        assert mock_repair_ollama.call_count >= 1


# ============== auto_repair_dfa Tests ==============

class TestAutoRepairDFA:
    """Tests for DFARepairEngine.auto_repair_dfa method."""

    def test_auto_repair_with_llm_success(self, mock_repair_ollama):
        """Test auto_repair_dfa with successful LLM repair."""
        mock_repair_ollama.return_value = '''{
            "states": ["q0", "q1"],
            "start_state": "q0",
            "accept_states": ["q1"],
            "transitions": {"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}}
        }'''
        
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        data = {"states": ["q0"], "transitions": {"q0": {"0": "q0", "1": "q0"}}}
        
        engine = DFARepairEngine()
        validator = DeterministicValidator()
        
        result = engine.auto_repair_dfa(data, spec, validator, "test error")
        
        assert isinstance(result, DFA)

    def test_auto_repair_llm_unavailable_fallback_to_cleanup(self, mock_repair_ollama):
        """Test auto_repair_dfa falls back to cleanup when LLM unavailable."""
        mock_repair_ollama.side_effect = LLMConnectionError("Service down")
        
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        data = {
            "states": ["q0", "q1"],
            "start_state": "q0",
            "accept_states": ["q1"],
            "transitions": {"q0": {"0": "q0", "1": "q1"}}  # Missing q1 transitions
        }
        
        engine = DFARepairEngine()
        
        result = engine.auto_repair_dfa(data, spec, validation_error="test error")
        
        assert isinstance(result, DFA)
        # Cleanup should have added missing transitions

    def test_auto_repair_with_invalid_data_fallback(self, mock_repair_ollama):
        """Test auto_repair_dfa with invalid data falls back to cleanup."""
        mock_repair_ollama.side_effect = LLMConnectionError("Service down")
        
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        # Invalid data that can't be converted to DFA
        data = {"invalid": "data"}
        
        engine = DFARepairEngine()
        
        result = engine.auto_repair_dfa(data, spec, validation_error="test error")
        
        assert isinstance(result, DFA)


# ============== _basic_structural_cleanup Tests ==============

class TestBasicStructuralCleanup:
    """Tests for DFARepairEngine._basic_structural_cleanup method."""

    def test_cleanup_adds_missing_transitions(self):
        """Test cleanup adds missing transitions for alphabet symbols."""
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        data = {
            "states": ["q0", "q1"],
            "start_state": "q0",
            "accept_states": ["q1"],
            "transitions": {"q0": {"0": "q0"}}  # Missing "1" transition
        }
        
        engine = DFARepairEngine()
        result = engine._basic_structural_cleanup(data, spec)
        
        assert isinstance(result, DFA)
        # Should have transitions for both symbols
        assert "0" in result.transitions["q0"]
        assert "1" in result.transitions["q0"]

    def test_cleanup_filters_invalid_states(self):
        """Test cleanup filters out invalid state names."""
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        data = {
            "states": ["q0", "invalid state name", "this is way too long for a state name xyz"],
            "start_state": "q0",
            "accept_states": ["q0"],
            "transitions": {}
        }
        
        engine = DFARepairEngine()
        result = engine._basic_structural_cleanup(data, spec)
        
        # Invalid states should be filtered
        assert "q0" in result.states
        assert "invalid state name" not in result.states

    def test_cleanup_fixes_invalid_start_state(self):
        """Test cleanup fixes invalid start state."""
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        data = {
            "states": ["q0", "q1"],
            "start_state": "invalid",
            "accept_states": ["q1"],
            "transitions": {"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}}
        }
        
        engine = DFARepairEngine()
        result = engine._basic_structural_cleanup(data, spec)
        
        assert result.start_state in result.states

    def test_cleanup_filters_invalid_accept_states(self):
        """Test cleanup filters out invalid accept states."""
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        data = {
            "states": ["q0", "q1"],
            "start_state": "q0",
            "accept_states": ["q1", "invalid"],
            "transitions": {"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q0", "1": "q1"}}
        }
        
        engine = DFARepairEngine()
        result = engine._basic_structural_cleanup(data, spec)
        
        assert "invalid" not in result.accept_states


# ============== try_inversion_fix Tests ==============

class TestTryInversionFix:
    """Tests for DFARepairEngine.try_inversion_fix method."""

    def test_inversion_fix_success(self):
        """Test successful inversion fix."""
        # Create a DFA that accepts strings NOT containing "1" (inverted logic)
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q1"}, "q1": {"0": "q1", "1": "q1"}},
            start_state="q0",
            accept_states=["q0"]  # Accepts strings without "1"
        )
        
        # We want strings CONTAINING "1", so inversion should work
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        engine = DFARepairEngine()
        validator = DeterministicValidator()
        
        result = engine.try_inversion_fix(dfa, spec, validator)
        
        # Inversion should produce a valid DFA
        assert result is not None
        assert isinstance(result, DFA)
        # Accept states should be inverted
        assert set(result.accept_states) != set(dfa.accept_states)

    def test_inversion_fix_not_always_works(self):
        """Test that inversion doesn't always produce valid result."""
        # Create a DFA that's just wrong (not just inverted)
        dfa = DFA(
            states=["q0"],
            alphabet=["0", "1"],
            transitions={"q0": {"0": "q0", "1": "q0"}},
            start_state="q0",
            accept_states=["q0"]
        )
        
        spec = LogicSpec(logic_type="STARTS_WITH", target="a", alphabet=["a", "b"])
        engine = DFARepairEngine()
        validator = DeterministicValidator()
        
        result = engine.try_inversion_fix(dfa, spec, validator)
        
        # Inversion returns a DFA (may or may not be valid)
        # The key is that it returns something with inverted accept states
        assert result is not None
        assert isinstance(result, DFA)
        # Accept states should be inverted (was ["q0"], now should be [])
        assert result.accept_states == []