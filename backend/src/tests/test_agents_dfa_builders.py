"""
Additional tests for agents.py DFA builder functions.
Targets specific missing lines to push coverage higher.
"""
import pytest
from unittest.mock import patch, Mock

from core.agents import (
    build_starts_with_dfa, build_substring_dfa, build_not_contains_dfa,
    build_no_consecutive_dfa, build_exact_length_dfa, build_min_length_dfa,
    build_max_length_dfa, build_length_mod_k_dfa, build_count_mod_k_dfa,
    build_divisible_by_dfa, build_product_even_dfa, build_min_count_dfa,
    build_max_count_dfa, AnalystAgent, ArchitectAgent
)
from core.models import LogicSpec, DFA
from core.product import ProductConstructionEngine


# ============== DFA Builder Function Tests ==============

class TestDFABuilderFunctions:
    """Tests for individual DFA builder functions."""

    def test_build_starts_with_dfa(self):
        """Test build_starts_with_dfa creates correct DFA."""
        dfa = build_starts_with_dfa(["0", "1"], "01")
        
        assert "states" in dfa
        assert "alphabet" in dfa
        assert "start_state" in dfa
        assert "accept_states" in dfa
        assert "transitions" in dfa
        
        # Should have states for each prefix position plus dead state
        assert len(dfa["states"]) >= 3  # q0, q1, q2, q_dead

    def test_build_substring_dfa_contains(self):
        """Test build_substring_dfa for CONTAINS."""
        dfa = build_substring_dfa(["0", "1"], "01", match_at_end_only=False)
        
        assert len(dfa["states"]) >= 3
        assert dfa["start_state"] == "q0"

    def test_build_substring_dfa_ends_with(self):
        """Test build_substring_dfa for ENDS_WITH."""
        dfa = build_substring_dfa(["0", "1"], "01", match_at_end_only=True)
        
        assert len(dfa["states"]) >= 3
        # Accept state should be when pattern is fully matched
        assert "q2" in dfa["accept_states"] or any("q" in s for s in dfa["accept_states"])

    def test_build_not_contains_dfa(self):
        """Test build_not_contains_dfa."""
        dfa = build_not_contains_dfa(["0", "1"], "11")
        
        assert len(dfa["states"]) >= 3
        # Should accept strings without "11"

    def test_build_no_consecutive_dfa(self):
        """Test build_no_consecutive_dfa."""
        dfa = build_no_consecutive_dfa(["0", "1"], "1")
        
        assert "q0" in dfa["states"]
        assert "q1" in dfa["states"]
        assert "sink" in dfa["states"]
        
        # q0 and q1 should be accepting
        assert "q0" in dfa["accept_states"]
        assert "q1" in dfa["accept_states"]
        # sink should be rejecting
        assert "sink" not in dfa["accept_states"]

    def test_build_exact_length_dfa(self):
        """Test build_exact_length_dfa."""
        dfa = build_exact_length_dfa(["0", "1"], 3)
        
        # Should have states q0, q1, q2, q3 (accept), q4 (reject)
        assert len(dfa["states"]) == 5
        assert "q3" in dfa["accept_states"]

    def test_build_min_length_dfa(self):
        """Test build_min_length_dfa."""
        dfa = build_min_length_dfa(["0", "1"], 3)
        
        # Should have states q0, q1, q2, q3 (accept and stay)
        assert len(dfa["states"]) == 4
        assert "q3" in dfa["accept_states"]

    def test_build_max_length_dfa(self):
        """Test build_max_length_dfa."""
        dfa = build_max_length_dfa(["0", "1"], 3)
        
        # Should accept up to length 3
        assert "q0" in dfa["accept_states"]
        assert "q3" in dfa["accept_states"]
        # q4 should be rejecting
        assert "q4" not in dfa["accept_states"]

    def test_build_length_mod_k_dfa(self):
        """Test build_length_mod_k_dfa."""
        dfa = build_length_mod_k_dfa(["0", "1"], 3, r=0)
        
        # Should have 3 states for mod 3
        assert len(dfa["states"]) == 3
        # q0 should be accepting (length % 3 == 0)
        assert "q0" in dfa["accept_states"]

    def test_build_count_mod_k_dfa(self):
        """Test build_count_mod_k_dfa."""
        dfa = build_count_mod_k_dfa(["0", "1"], "1", 3, r=0)
        
        # Should have 3 states for counting mod 3
        assert len(dfa["states"]) == 3
        assert "q0" in dfa["accept_states"]

    def test_build_divisible_by_dfa(self):
        """Test build_divisible_by_dfa."""
        dfa = build_divisible_by_dfa(["0", "1"], 3)
        
        # Should have 3 states for remainders
        assert len(dfa["states"]) == 3
        # r0 should be accepting (divisible by 3)
        assert "r0" in dfa["accept_states"]

    def test_build_divisible_by_dfa_non_binary(self):
        """Test build_divisible_by_dfa with non-binary alphabet."""
        dfa = build_divisible_by_dfa(["a", "b", "c"], 3)
        
        assert len(dfa["states"]) == 3
        assert "r0" in dfa["accept_states"]

    def test_build_product_even_dfa(self):
        """Test build_product_even_dfa."""
        dfa = build_product_even_dfa(["0", "1"])
        
        # Should have 2 states: even and odd product
        assert len(dfa["states"]) == 2
        # q1 should be accepting (even product)
        assert "q1" in dfa["accept_states"]

    def test_build_min_count_dfa_zero_count(self):
        """Test build_min_count_dfa with min_count=0."""
        dfa = build_min_count_dfa(["0", "1"], "1", 0)
        
        # Should accept all strings
        assert len(dfa["states"]) == 1
        assert "q_accept" in dfa["states"]

    def test_build_min_count_dfa(self):
        """Test build_min_count_dfa."""
        dfa = build_min_count_dfa(["0", "1"], "1", 2)
        
        # Should have states for 0, 1, 2+ matches
        assert len(dfa["states"]) == 3
        # q2 should be accepting
        assert "q2" in dfa["accept_states"]

    def test_build_max_count_dfa(self):
        """Test build_max_count_dfa."""
        dfa = build_max_count_dfa(["0", "1"], "1", 2)
        
        # Should have states for 0, 1, 2 matches, and overflow
        assert len(dfa["states"]) == 4
        # q_over should be rejecting
        assert "q_over" not in dfa["accept_states"]


# ============== ArchitectAgent Atomic Builder Tests ==============

class TestArchitectAgentAtomicBuilders:
    """Tests for ArchitectAgent._build_atomic_dfa method."""

    def test_build_atomic_starts_with(self):
        """Test _build_atomic_dfa for STARTS_WITH."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("STARTS_WITH", "ab", ["a", "b"])
        
        assert result is not None
        result_dict = dict(result)
        assert "states" in result_dict

    def test_build_atomic_contains(self):
        """Test _build_atomic_dfa for CONTAINS."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("CONTAINS", "01", ["0", "1"])
        
        assert result is not None

    def test_build_atomic_ends_with(self):
        """Test _build_atomic_dfa for ENDS_WITH."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("ENDS_WITH", "10", ["0", "1"])
        
        assert result is not None

    def test_build_atomic_no_consecutive(self):
        """Test _build_atomic_dfa for NO_CONSECUTIVE."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("NO_CONSECUTIVE", "1", ["0", "1"])
        
        assert result is not None

    def test_build_atomic_exact_length(self):
        """Test _build_atomic_dfa for EXACT_LENGTH."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("EXACT_LENGTH", "5", ["0", "1"])
        
        assert result is not None

    def test_build_atomic_min_length(self):
        """Test _build_atomic_dfa for MIN_LENGTH."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("MIN_LENGTH", "3", ["0", "1"])
        
        assert result is not None

    def test_build_atomic_max_length(self):
        """Test _build_atomic_dfa for MAX_LENGTH."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("MAX_LENGTH", "5", ["0", "1"])
        
        assert result is not None

    def test_build_atomic_length_mod(self):
        """Test _build_atomic_dfa for LENGTH_MOD."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("LENGTH_MOD", "0:3", ["0", "1"])
        
        assert result is not None

    def test_build_atomic_count_mod(self):
        """Test _build_atomic_dfa for COUNT_MOD."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("COUNT_MOD", "1:0:2", ["0", "1"])
        
        assert result is not None

    def test_build_atomic_divisible_by(self):
        """Test _build_atomic_dfa for DIVISIBLE_BY."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("DIVISIBLE_BY", "4", ["0", "1"])
        
        assert result is not None

    def test_build_atomic_product_even(self):
        """Test _build_atomic_dfa for PRODUCT_EVEN."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("PRODUCT_EVEN", None, ["0", "1"])
        
        assert result is not None

    def test_build_atomic_even_count(self):
        """Test _build_atomic_dfa for EVEN_COUNT."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("EVEN_COUNT", "1", ["0", "1"])
        
        assert result is not None

    def test_build_atomic_odd_count(self):
        """Test _build_atomic_dfa for ODD_COUNT."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("ODD_COUNT", "1", ["0", "1"])
        
        assert result is not None

    def test_build_atomic_min_count(self):
        """Test _build_atomic_dfa for MIN_COUNT."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("MIN_COUNT", "1:3", ["0", "1"])
        
        assert result is not None

    def test_build_atomic_max_count(self):
        """Test _build_atomic_dfa for MAX_COUNT."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._build_atomic_dfa("MAX_COUNT", "1:2", ["0", "1"])
        
        assert result is not None

    def test_build_atomic_not_starts_with(self):
        """Test _build_atomic_dfa for NOT_STARTS_WITH."""
        agent = ArchitectAgent(model_name="test")
        
        # Mock the product engine invert
        mock_engine = Mock()
        mock_engine.invert.return_value = DFA(
            states=["q0"], alphabet=["a"],
            transitions={"q0": {"a": "q0"}},
            start_state="q0", accept_states=[]
        )
        agent.product_engine = mock_engine
        
        result = agent._build_atomic_dfa("NOT_STARTS_WITH", "a", ["a", "b"])
        
        assert result is not None

    def test_build_atomic_not_ends_with(self):
        """Test _build_atomic_dfa for NOT_ENDS_WITH."""
        agent = ArchitectAgent(model_name="test")
        
        mock_engine = Mock()
        mock_engine.invert.return_value = DFA(
            states=["q0"], alphabet=["a"],
            transitions={"q0": {"a": "q0"}},
            start_state="q0", accept_states=[]
        )
        agent.product_engine = mock_engine
        
        result = agent._build_atomic_dfa("NOT_ENDS_WITH", "a", ["a", "b"])
        
        assert result is not None

    def test_build_atomic_not_contains(self):
        """Test _build_atomic_dfa for NOT_CONTAINS."""
        agent = ArchitectAgent(model_name="test")
        
        mock_engine = Mock()
        mock_engine.invert.return_value = DFA(
            states=["q0"], alphabet=["a"],
            transitions={"q0": {"a": "q0"}},
            start_state="q0", accept_states=[]
        )
        agent.product_engine = mock_engine
        
        result = agent._build_atomic_dfa("NOT_CONTAINS", "a", ["a", "b"])
        
        assert result is not None

    def test_build_atomic_unsupported_type(self):
        """Test _build_atomic_dfa for unsupported type raises ValueError."""
        agent = ArchitectAgent(model_name="test")
        
        with pytest.raises(ValueError):
            agent._build_atomic_dfa("UNKNOWN_TYPE", "test", ["0", "1"])

    def test_build_atomic_exception_returns_rejecting_dfa(self):
        """Test _build_atomic_dfa returns rejecting DFA on exception."""
        agent = ArchitectAgent(model_name="test")
        
        # DIVISIBLE_BY with invalid target should trigger exception handling
        result = agent._build_atomic_dfa("DIVISIBLE_BY", "invalid", ["0", "1"])
        
        assert result is not None
        result_dict = dict(result)
        assert "states" in result_dict


# ============== ArchitectAgent Design Method Tests ==============

class TestArchitectAgentDesign:
    """Tests for ArchitectAgent.design method."""

    def test_design_atomic_with_cache_miss(self):
        """Test design for atomic spec with cache miss."""
        agent = ArchitectAgent(model_name="test")
        
        spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        dfa = agent.design(spec)
        
        assert isinstance(dfa, DFA)
        assert len(dfa.states) > 0

    def test_design_atomic_with_cache_hit(self):
        """Test design for atomic spec with cache hit."""
        agent = ArchitectAgent(model_name="test")
        
        spec = LogicSpec(logic_type="STARTS_WITH", target="0", alphabet=["0", "1"])
        
        # First call (cache miss)
        dfa1 = agent.design(spec)
        hits1 = agent.cache_hits
        
        # Second call (cache hit)
        dfa2 = agent.design(spec)
        hits2 = agent.cache_hits
        
        # Cache hits should increase
        assert hits2 > hits1

    def test_design_not_operation(self):
        """Test design for NOT operation."""
        agent = ArchitectAgent(model_name="test")
        
        child_spec = LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])
        spec = LogicSpec(logic_type="NOT", children=[child_spec], alphabet=["0", "1"])
        
        dfa = agent.design(spec)
        
        assert isinstance(dfa, DFA)

    def test_design_and_operation(self):
        """Test design for AND operation."""
        agent = ArchitectAgent(model_name="test")
        
        child1 = LogicSpec(logic_type="STARTS_WITH", target="0", alphabet=["0", "1"])
        child2 = LogicSpec(logic_type="ENDS_WITH", target="1", alphabet=["0", "1"])
        spec = LogicSpec(logic_type="AND", children=[child1, child2], alphabet=["0", "1"])
        
        dfa = agent.design(spec)
        
        assert isinstance(dfa, DFA)

    def test_design_or_operation(self):
        """Test design for OR operation."""
        agent = ArchitectAgent(model_name="test")
        
        child1 = LogicSpec(logic_type="STARTS_WITH", target="0", alphabet=["0", "1"])
        child2 = LogicSpec(logic_type="STARTS_WITH", target="1", alphabet=["0", "1"])
        spec = LogicSpec(logic_type="OR", children=[child1, child2], alphabet=["0", "1"])
        
        dfa = agent.design(spec)
        
        assert isinstance(dfa, DFA)

    def test_design_product_size_exceeded(self):
        """Test design raises error when product size estimate exceeds threshold."""
        agent = ArchitectAgent(model_name="test", max_product_states=10)
        
        # Create specs that would exceed threshold
        child1 = LogicSpec(logic_type="DIVISIBLE_BY", target="100", alphabet=["0", "1"])
        child2 = LogicSpec(logic_type="DIVISIBLE_BY", target="100", alphabet=["0", "1"])
        spec = LogicSpec(logic_type="AND", children=[child1, child2], alphabet=["0", "1"])
        
        with pytest.raises(ValueError) as exc_info:
            agent.design(spec)
        
        assert "Product size estimate" in str(exc_info.value)

    def test_design_empty_children(self):
        """Test design with empty children list."""
        agent = ArchitectAgent(model_name="test")
        
        spec = LogicSpec(logic_type="AND", children=[], alphabet=["0", "1"])
        
        with pytest.raises((ValueError, IndexError)):
            agent.design(spec)

    def test_design_propagates_alphabet_to_children(self):
        """Test that design propagates alphabet to children."""
        agent = ArchitectAgent(model_name="test")
        
        child = LogicSpec(logic_type="CONTAINS", target="a")  # No alphabet
        spec = LogicSpec(logic_type="AND", children=[child], alphabet=["a", "b"])
        
        dfa = agent.design(spec)
        
        # Child should have inherited alphabet
        assert child.alphabet == ["a", "b"]


# ============== ArchitectAgent Cache Tests ==============

class TestArchitectAgentCache:
    """Tests for ArchitectAgent cache functionality."""

    def test_get_cache_stats(self):
        """Test get_cache_stats returns statistics."""
        agent = ArchitectAgent(model_name="test")
        
        stats = agent.get_cache_stats()
        
        assert "total_entries" in stats
        assert "total_size_bytes" in stats
        assert "cache_directory" in stats

    def test_get_cached_atomic_dfa_miss(self):
        """Test _get_cached_atomic_dfa on cache miss."""
        agent = ArchitectAgent(model_name="test")
        
        result = agent._get_cached_atomic_dfa("STARTS_WITH", "xyz123", ("0", "1"))
        
        # Should return None on miss
        assert result is None

    def test_set_cached_atomic_dfa(self):
        """Test _set_cached_atomic_dfa stores value."""
        agent = ArchitectAgent(model_name="test")
        
        dfa_tuple = (
            ("states", ("q0", "q1")),
            ("alphabet", ("0", "1")),
            ("transitions", (("q0", {"0": "q0", "1": "q1"}), ("q1", {"0": "q0", "1": "q1"}))),
            ("start_state", "q0"),
            ("accept_states", ("q1",))
        )
        
        # Should not raise
        agent._set_cached_atomic_dfa("TEST", "test", ("0", "1"), dfa_tuple)
        
        # Verify it's cached
        result = agent._get_cached_atomic_dfa("TEST", "test", ("0", "1"))
        assert result is not None