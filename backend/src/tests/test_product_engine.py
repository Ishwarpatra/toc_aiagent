"""
Comprehensive tests for ProductConstructionEngine.
Tests intersection, union, complement (invert), and minimization logic.
"""

import pytest
from core.product import ProductConstructionEngine
from core.models import DFA


# Helper to create simple DFAs for testing
def create_dfa_starts_with_a():
    """DFA that accepts strings starting with 'a' over alphabet {a, b}."""
    return DFA(
        states=["q0", "q1", "q_dead"],
        alphabet=["a", "b"],
        transitions={
            "q0": {"a": "q1", "b": "q_dead"},
            "q1": {"a": "q1", "b": "q1"},
            "q_dead": {"a": "q_dead", "b": "q_dead"}
        },
        start_state="q0",
        accept_states=["q1"]
    )


def create_dfa_ends_with_b():
    """DFA that accepts strings ending with 'b' over alphabet {a, b}."""
    return DFA(
        states=["q0", "q1"],
        alphabet=["a", "b"],
        transitions={
            "q0": {"a": "q0", "b": "q1"},
            "q1": {"a": "q0", "b": "q1"}
        },
        start_state="q0",
        accept_states=["q1"]
    )


def create_dfa_contains_ab():
    """DFA that accepts strings containing 'ab' over alphabet {a, b}."""
    return DFA(
        states=["q0", "q1", "q2"],
        alphabet=["a", "b"],
        transitions={
            "q0": {"a": "q1", "b": "q0"},
            "q1": {"a": "q1", "b": "q2"},
            "q2": {"a": "q2", "b": "q2"}
        },
        start_state="q0",
        accept_states=["q2"]
    )


def simulate_dfa(dfa: DFA, s: str) -> bool:
    """Simulate DFA on input string and return True if accepted."""
    curr = dfa.start_state
    for char in s:
        if curr not in dfa.transitions:
            return False
        curr = dfa.transitions[curr].get(char)
        if curr is None:
            return False
    return curr in dfa.accept_states


class TestProductConstructionEngine:
    """Tests for ProductConstructionEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ProductConstructionEngine()

    # ==================== INTERSECTION (AND) TESTS ====================

    def test_intersection_starts_with_a_and_ends_with_b(self):
        """Test intersection: STARTS_WITH 'a' AND ENDS_WITH 'b'."""
        dfa1 = create_dfa_starts_with_a()
        dfa2 = create_dfa_ends_with_b()

        combined = self.engine.combine(dfa1, dfa2, "AND")

        # Should accept: "ab", "aab", "abb", "aaab"
        assert simulate_dfa(combined, "ab") is True
        assert simulate_dfa(combined, "aab") is True
        assert simulate_dfa(combined, "abb") is True
        assert simulate_dfa(combined, "aaab") is True

        # Should reject: "a" (doesn't end with b), "b" (doesn't start with a), "ba"
        assert simulate_dfa(combined, "a") is False
        assert simulate_dfa(combined, "b") is False
        assert simulate_dfa(combined, "ba") is False
        assert simulate_dfa(combined, "aba") is False

    def test_intersection_contains_ab_and_ends_with_b(self):
        """Test intersection: CONTAINS 'ab' AND ENDS_WITH 'b'."""
        dfa1 = create_dfa_contains_ab()
        dfa2 = create_dfa_ends_with_b()

        combined = self.engine.combine(dfa1, dfa2, "AND")

        # Should accept: "ab", "aab", "abb", "aaab"
        assert simulate_dfa(combined, "ab") is True
        assert simulate_dfa(combined, "aab") is True
        assert simulate_dfa(combined, "abb") is True

        # Should reject: "a" (no 'ab'), "aba" (doesn't end with b)
        assert simulate_dfa(combined, "a") is False
        assert simulate_dfa(combined, "aba") is False

    # ==================== UNION (OR) TESTS ====================

    def test_union_starts_with_a_or_ends_with_b(self):
        """Test union: STARTS_WITH 'a' OR ENDS_WITH 'b'."""
        dfa1 = create_dfa_starts_with_a()
        dfa2 = create_dfa_ends_with_b()

        combined = self.engine.combine(dfa1, dfa2, "OR")

        # Should accept: "a" (starts with a), "b" (ends with b), "ab" (both)
        assert simulate_dfa(combined, "a") is True
        assert simulate_dfa(combined, "b") is True
        assert simulate_dfa(combined, "ab") is True
        assert simulate_dfa(combined, "aa") is True
        assert simulate_dfa(combined, "bb") is True

        # Should reject: "ba" (starts with b, ends with a)
        assert simulate_dfa(combined, "ba") is False
        assert simulate_dfa(combined, "bba") is False

    def test_union_contains_ab_or_ends_with_b(self):
        """Test union: CONTAINS 'ab' OR ENDS_WITH 'b'."""
        dfa1 = create_dfa_contains_ab()
        dfa2 = create_dfa_ends_with_b()

        combined = self.engine.combine(dfa1, dfa2, "OR")

        # Should accept: "ab" (contains ab), "b" (ends with b), "aab" (both)
        assert simulate_dfa(combined, "ab") is True
        assert simulate_dfa(combined, "b") is True
        assert simulate_dfa(combined, "aab") is True
        assert simulate_dfa(combined, "bb") is True

        # Should reject: "a" (no 'ab', doesn't end with b)
        assert simulate_dfa(combined, "a") is False
        assert simulate_dfa(combined, "aa") is False

    # ==================== COMPLEMENT (NOT/INVERT) TESTS ====================

    def test_invert_starts_with_a(self):
        """Test complement: NOT STARTS_WITH 'a' = starts with 'b' or empty."""
        dfa = create_dfa_starts_with_a()
        inverted = self.engine.invert(dfa)

        # Should accept: "b", "ba", "bb", "" (empty - doesn't start with 'a')
        assert simulate_dfa(inverted, "b") is True
        assert simulate_dfa(inverted, "ba") is True
        assert simulate_dfa(inverted, "bb") is True

        # Should reject: "a", "ab", "aa" (all start with 'a')
        assert simulate_dfa(inverted, "a") is False
        assert simulate_dfa(inverted, "ab") is False
        assert simulate_dfa(inverted, "aa") is False

    def test_invert_ends_with_b(self):
        """Test complement: NOT ENDS_WITH 'b' = ends with 'a' or empty."""
        dfa = create_dfa_ends_with_b()
        inverted = self.engine.invert(dfa)

        # Should accept: "a", "aa", "ba", "" (empty)
        assert simulate_dfa(inverted, "a") is True
        assert simulate_dfa(inverted, "aa") is True
        assert simulate_dfa(inverted, "ba") is True

        # Should reject: "b", "ab", "bb" (all end with 'b')
        assert simulate_dfa(inverted, "b") is False
        assert simulate_dfa(inverted, "ab") is False
        assert simulate_dfa(inverted, "bb") is False

    # ==================== MINIMIZATION TESTS ====================

    def test_minimize_already_minimal(self):
        """Test that already-minimal DFA stays the same."""
        dfa = create_dfa_ends_with_b()
        minimized = self.engine.minimize(dfa)

        # Should still accept same language
        for s in ["", "a", "b", "ab", "ba", "bb", "aab", "abb"]:
            assert simulate_dfa(minimized, s) == simulate_dfa(dfa, s)

    def test_minimize_removes_unreachable_states(self):
        """Test that unreachable states are removed."""
        # Create DFA with unreachable state
        dfa = DFA(
            states=["q0", "q1", "q_unreachable"],
            alphabet=["a", "b"],
            transitions={
                "q0": {"a": "q1", "b": "q1"},
                "q1": {"a": "q1", "b": "q1"},
                "q_unreachable": {"a": "q_unreachable", "b": "q_unreachable"}
            },
            start_state="q0",
            accept_states=["q1"]
        )

        minimized = self.engine.minimize(dfa)

        # Unreachable state should be removed
        assert "q_unreachable" not in minimized.states

        # Language should be preserved (accepts all non-empty strings)
        assert simulate_dfa(minimized, "a") is True
        assert simulate_dfa(minimized, "b") is True
        assert simulate_dfa(minimized, "ab") is True

    def test_minimize_merges_equivalent_states(self):
        """Test that equivalent states are merged."""
        # Create DFA with equivalent states
        dfa = DFA(
            states=["q0", "q1", "q2"],
            alphabet=["a", "b"],
            transitions={
                "q0": {"a": "q1", "b": "q2"},
                "q1": {"a": "q1", "b": "q1"},
                "q2": {"a": "q2", "b": "q2"}
            },
            start_state="q0",
            accept_states=["q1", "q2"]  # q1 and q2 are equivalent
        )

        minimized = self.engine.minimize(dfa)

        # Should have fewer states (q1 and q2 merged)
        assert len(minimized.states) < len(dfa.states)

        # Language should be preserved
        test_strings = ["", "a", "b", "aa", "ab", "ba", "bb"]
        for s in test_strings:
            assert simulate_dfa(minimized, s) == simulate_dfa(dfa, s), f"Failed for: {s}"

    def test_minimize_single_state_accept(self):
        """Test minimization of single accept state DFA."""
        dfa = DFA(
            states=["q0"],
            alphabet=["a", "b"],
            transitions={
                "q0": {"a": "q0", "b": "q0"}
            },
            start_state="q0",
            accept_states=["q0"]
        )

        minimized = self.engine.minimize(dfa)
        assert len(minimized.states) == 1
        assert simulate_dfa(minimized, "") is True
        assert simulate_dfa(minimized, "a") is True

    def test_minimize_single_state_reject(self):
        """Test minimization of single reject state DFA."""
        dfa = DFA(
            states=["q0"],
            alphabet=["a", "b"],
            transitions={
                "q0": {"a": "q0", "b": "q0"}
            },
            start_state="q0",
            accept_states=[]
        )

        minimized = self.engine.minimize(dfa)
        assert len(minimized.states) == 1
        assert simulate_dfa(minimized, "") is False
        assert simulate_dfa(minimized, "a") is False

    # ==================== EDGE CASES ====================

    def test_combine_same_dfa(self):
        """Test combining same DFA with itself."""
        dfa = create_dfa_starts_with_a()

        combined = self.engine.combine(dfa, dfa, "AND")

        # Should accept same language as original
        assert simulate_dfa(combined, "a") is True
        assert simulate_dfa(combined, "ab") is True
        assert simulate_dfa(combined, "b") is False

    def test_invert_double_invert(self):
        """Test that double inversion returns original."""
        dfa = create_dfa_starts_with_a()
        
        inverted = self.engine.invert(dfa)
        double_inverted = self.engine.invert(inverted)

        # Double inverted should accept same language as original
        test_strings = ["", "a", "b", "ab", "ba", "bb"]
        for s in test_strings:
            assert simulate_dfa(double_inverted, s) == simulate_dfa(dfa, s)
