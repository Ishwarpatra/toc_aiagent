"""
Tests for agents.py LLM mocking and JSON parsing.
Tests the neuro-symbolic routing of the application.
"""
import pytest
import json
from unittest.mock import patch, MagicMock

from core.agents import (
    BaseAgent, AnalystAgent, ArchitectAgent,
    split_top_level, unify_alphabets_for_spec, flatten_children,
    estimate_states_for_spec
)
from core.models import LogicSpec, DFA


# ============== BaseAgent LLM Mocking Tests ==============

class TestBaseAgentLLM:
    """Tests for BaseAgent.call_ollama mocking."""

    def test_call_ollama_stub_returns_none(self):
        """BaseAgent.call_ollama is a stub that returns None by default."""
        agent = BaseAgent(model_name="test")
        result = agent.call_ollama("system prompt", "user prompt")
        assert result is None

    def test_call_ollama_with_mock(self, mock_ollama_response):
        """Test mocking BaseAgent.call_ollama."""
        mock_ollama_response.return_value = '{"result": "test"}'
        agent = BaseAgent(model_name="test")
        result = agent.call_ollama("system", "user")
        assert result == '{"result": "test"}'
        mock_ollama_response.assert_called_once_with("system", "user")


# ============== AnalystAgent LLM Parsing Tests ==============

class TestAnalystAgentLLMParsing:
    """
    Tests for AnalystAgent LLM-based parsing.
    Tests valid parsing and retry logic for malformed JSON.
    """

    def test_analyze_with_valid_llm_json(self, mock_ollama_response):
        """Test 1: Valid parsing - Return a perfect JSON DFA and assert AnalystAgent returns the object."""
        valid_json = '''{
            "logic_type": "CONTAINS",
            "target": "01",
            "alphabet": ["0", "1"]
        }'''
        mock_ollama_response.return_value = valid_json
        
        agent = AnalystAgent(model_name="test")
        # Use a prompt that won't be parsed locally, forcing LLM fallback
        spec = agent.analyze("some complex pattern xyz123")
        
        assert spec.logic_type == "CONTAINS"
        assert spec.target == "01"
        assert spec.alphabet == ["0", "1"]

    def test_analyze_with_type_key_normalization(self, mock_ollama_response):
        """Test LLM response with 'type' key normalized to 'logic_type'."""
        # Some LLMs might use 'type' instead of 'logic_type'
        valid_json = '''{
            "type": "STARTS_WITH",
            "target": "abc",
            "alphabet": ["a", "b", "c"]
        }'''
        mock_ollama_response.return_value = valid_json
        
        agent = AnalystAgent(model_name="test")
        spec = agent.analyze("another complex pattern")
        
        assert spec.logic_type == "STARTS_WITH"
        assert spec.target == "abc"

    def test_analyze_with_constraints_key_normalization(self, mock_ollama_response):
        """Test LLM response with 'constraints' key normalized to 'children'."""
        valid_json = '''{
            "logic_type": "AND",
            "target": null,
            "constraints": [
                {"logic_type": "STARTS_WITH", "target": "a"},
                {"logic_type": "ENDS_WITH", "target": "b"}
            ]
        }'''
        mock_ollama_response.return_value = valid_json
        
        agent = AnalystAgent(model_name="test")
        spec = agent.analyze("yet another complex pattern")
        
        assert spec.logic_type == "AND"
        assert len(spec.children) == 2

    def test_analyze_with_markdown_code_block(self, mock_ollama_response):
        """Test LLM response wrapped in markdown code blocks."""
        wrapped_json = '''```json
        {
            "logic_type": "ENDS_WITH",
            "target": "test",
            "alphabet": ["t", "e", "s"]
        }
        ```'''
        mock_ollama_response.return_value = wrapped_json
        
        agent = AnalystAgent(model_name="test")
        spec = agent.analyze("pattern requiring LLM")
        
        assert spec.logic_type == "ENDS_WITH"
        assert spec.target == "test"

    def test_analyze_llm_parse_failure_falls_back_to_default(self, mock_ollama_response):
        """Test that LLM parse failure falls back to default LogicSpec."""
        # Return invalid JSON that can't be parsed
        mock_ollama_response.return_value = "not valid json at all"
        
        agent = AnalystAgent(model_name="test")
        spec = agent.analyze("pattern that will fail LLM parse")
        
        # Should fall back to default CONTAINS '1'
        assert spec.logic_type == "CONTAINS"
        assert spec.target == "1"

    def test_analyze_llm_returns_none_falls_back_to_default(self, mock_ollama_response):
        """Test that None LLM response falls back to default."""
        mock_ollama_response.return_value = None
        
        agent = AnalystAgent(model_name="test")
        spec = agent.analyze("pattern with no LLM response")
        
        assert spec.logic_type == "CONTAINS"
        assert spec.target == "1"

    def test_analyze_local_composite_parse_and(self):
        """Test local composite parsing for AND operations."""
        agent = AnalystAgent(model_name="test")
        spec = agent.analyze("strings that start with 'a' and end with 'b'")
        
        assert spec.logic_type == "AND"
        assert len(spec.children) >= 2

    def test_analyze_local_composite_parse_or(self):
        """Test local composite parsing for OR operations."""
        agent = AnalystAgent(model_name="test")
        spec = agent.analyze("strings that start with 'a' or end with 'b'")
        
        assert spec.logic_type == "OR"
        assert len(spec.children) >= 2

    def test_analyze_range_query(self):
        """Test range query parsing: count of X between A and B."""
        agent = AnalystAgent(model_name="test")
        spec = agent.analyze("count of 1 between 2 and 4")
        
        assert spec.logic_type == "AND"
        assert len(spec.children) == 2
        # Should have MIN_COUNT and MAX_COUNT
        logic_types = [c.logic_type for c in spec.children]
        assert "MIN_COUNT" in logic_types
        assert "MAX_COUNT" in logic_types


# ============== Helper Function Tests ==============

class TestAgentHelperFunctions:
    """Tests for helper functions in agents.py."""

    def test_split_top_level_simple(self):
        """Test split_top_level with simple separator."""
        result = split_top_level("a and b and c", " and ")
        assert result == ["a", "b", "c"]

    def test_split_top_level_with_parentheses(self):
        """Test split_top_level ignores separators inside parentheses."""
        result = split_top_level("(a and b) or (c and d)", " or ")
        assert len(result) == 2
        assert "(a and b)" in result
        assert "(c and d)" in result

    def test_split_top_level_with_quotes(self):
        """Test split_top_level ignores separators inside quotes."""
        result = split_top_level("'a and b' or 'c'", " or ")
        assert len(result) == 2

    def test_unify_alphabets_for_spec_atomic(self):
        """Test unify_alphabets_for_spec with atomic spec."""
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        result = unify_alphabets_for_spec(spec)
        assert result == ["0", "1"]

    def test_unify_alphabets_for_spec_no_alphabet_defaults(self):
        """Test unify_alphabets_for_spec defaults to ['0', '1'] when no alphabet."""
        spec = LogicSpec(logic_type="CONTAINS", target="1")
        result = unify_alphabets_for_spec(spec)
        assert result == ["0", "1"]

    def test_unify_alphabets_for_spec_composite(self):
        """Test unify_alphabets_for_spec merges alphabets from children."""
        child1 = LogicSpec(logic_type="STARTS_WITH", target="a", alphabet=["a", "b"])
        child2 = LogicSpec(logic_type="ENDS_WITH", target="0", alphabet=["0", "1"])
        spec = LogicSpec(logic_type="AND", children=[child1, child2])
        
        result = unify_alphabets_for_spec(spec)
        # Should merge all alphabets
        assert "a" in result
        assert "b" in result
        assert "0" in result
        assert "1" in result

    def test_flatten_children_no_children(self):
        """Test flatten_children with no children returns empty list."""
        spec = LogicSpec(logic_type="CONTAINS", target="1")
        result = flatten_children(spec)
        assert result == []

    def test_flatten_children_nested_same_operator(self):
        """Test flatten_children flattens nested same operators."""
        child1 = LogicSpec(logic_type="AND", target="a")
        child2 = LogicSpec(logic_type="AND", target="b")
        parent = LogicSpec(logic_type="AND", children=[child1, child2])
        
        result = flatten_children(parent)
        assert len(result) == 2

    def test_estimate_states_for_spec_and(self):
        """Test estimate_states_for_spec for AND composite."""
        child1 = LogicSpec(logic_type="CONTAINS", target="1")
        child2 = LogicSpec(logic_type="STARTS_WITH", target="0")
        spec = LogicSpec(logic_type="AND", children=[child1, child2])
        
        result = estimate_states_for_spec(spec)
        assert result >= 1

    def test_estimate_states_for_spec_not(self):
        """Test estimate_states_for_spec for NOT."""
        child = LogicSpec(logic_type="CONTAINS", target="1")
        spec = LogicSpec(logic_type="NOT", children=[child])
        
        result = estimate_states_for_spec(spec)
        assert result >= 2

    def test_estimate_states_for_spec_starts_with(self):
        """Test estimate_states_for_spec for STARTS_WITH."""
        spec = LogicSpec(logic_type="STARTS_WITH", target="abc")
        result = estimate_states_for_spec(spec)
        # Should be len(pattern) + 1
        assert result == len("abc") + 1

    def test_estimate_states_for_spec_divisible_by(self):
        """Test estimate_states_for_spec for DIVISIBLE_BY."""
        spec = LogicSpec(logic_type="DIVISIBLE_BY", target="5")
        result = estimate_states_for_spec(spec)
        assert result == 5

    def test_estimate_states_for_spec_no_consecutive(self):
        """Test estimate_states_for_spec for NO_CONSECUTIVE."""
        spec = LogicSpec(logic_type="NO_CONSECUTIVE", target="1")
        result = estimate_states_for_spec(spec)
        assert result == 3


# ============== ArchitectAgent LLM Tests ==============

class TestArchitectAgentLLM:
    """Tests for ArchitectAgent LLM fallback."""

    def test_design_with_llm_fallback(self, mock_ollama_response, valid_dfa_json):
        """Test ArchitectAgent uses LLM when atomic builder fails."""
        mock_ollama_response.return_value = valid_dfa_json
        
        agent = ArchitectAgent(model_name="test")
        # Create a spec that might trigger LLM fallback
        spec = LogicSpec(logic_type="UNKNOWN_TYPE", target="test", alphabet=["0", "1"])
        
        dfa = agent.design(spec)
        assert isinstance(dfa, DFA)
        assert dfa.states is not None

    def test_design_cache_miss_then_llm(self, mock_ollama_response, valid_dfa_json):
        """Test cache miss followed by LLM response."""
        mock_ollama_response.return_value = valid_dfa_json
        
        agent = ArchitectAgent(model_name="test")
        spec = LogicSpec(logic_type="UNKNOWN_OPERATION", target="xyz")
        
        dfa = agent.design(spec)
        assert isinstance(dfa, DFA)

    def test_design_returns_rejecting_dfa_on_llm_failure(self, mock_ollama_response):
        """Test that design returns rejecting DFA when LLM fails."""
        mock_ollama_response.return_value = None
        
        agent = ArchitectAgent(model_name="test")
        spec = LogicSpec(logic_type="UNKNOWN_TYPE", target="test")
        
        dfa = agent.design(spec)
        assert isinstance(dfa, DFA)
        assert len(dfa.states) >= 1
        # Should be a rejecting DFA (no accept states)
        assert len(dfa.accept_states) == 0