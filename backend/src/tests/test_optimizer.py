"""
Comprehensive tests for DFA Optimizer module.
Tests state minimization, unreachable state removal, and productivity analysis.
"""

import pytest
from core.optimizer import DFAOptimizer
from core.models import DFA


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


class TestDFAOptimizer:
    """Tests for DFAOptimizer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.optimizer = DFAOptimizer(verbose=False)

    # ==================== REACHABLE STATES TESTS ====================

    def test_find_reachable_all_reachable(self):
        """Test finding reachable states when all are reachable."""
        dfa = DFA(
            states=["q0", "q1", "q2"],
            alphabet=["a", "b"],
            transitions={
                "q0": {"a": "q1", "b": "q2"},
                "q1": {"a": "q2", "b": "q0"},
                "q2": {"a": "q0", "b": "q1"}
            },
            start_state="q0",
            accept_states=["q2"]
        )

        reachable = self.optimizer.find_reachable_states(dfa)
        assert reachable == {"q0", "q1", "q2"}

    def test_find_reachable_some_unreachable(self):
        """Test finding reachable states with unreachable states."""
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

        reachable = self.optimizer.find_reachable_states(dfa)
        assert reachable == {"q0", "q1"}
        assert "q_unreachable" not in reachable

    def test_find_reachable_chain(self):
        """Test finding reachable states in a chain."""
        dfa = DFA(
            states=["q0", "q1", "q2", "q3"],
            alphabet=["a"],
            transitions={
                "q0": {"a": "q1"},
                "q1": {"a": "q2"},
                "q2": {"a": "q3"},
                "q3": {"a": "q3"}
            },
            start_state="q0",
            accept_states=["q3"]
        )

        reachable = self.optimizer.find_reachable_states(dfa)
        assert reachable == {"q0", "q1", "q2", "q3"}

    def test_find_reachable_single_state(self):
        """Test finding reachable states with single state DFA."""
        dfa = DFA(
            states=["q0"],
            alphabet=["a"],
            transitions={"q0": {"a": "q0"}},
            start_state="q0",
            accept_states=[]
        )

        reachable = self.optimizer.find_reachable_states(dfa)
        assert reachable == {"q0"}

    # ==================== PRODUCTIVE STATES TESTS ====================

    def test_find_productive_all_productive(self):
        """Test finding productive states when all can reach accept."""
        dfa = DFA(
            states=["q0", "q1", "q2"],
            alphabet=["a", "b"],
            transitions={
                "q0": {"a": "q1", "b": "q2"},
                "q1": {"a": "q2", "b": "q2"},
                "q2": {"a": "q2", "b": "q2"}
            },
            start_state="q0",
            accept_states=["q2"]
        )

        productive = self.optimizer.find_productive_states(dfa)
        # All states can reach q2 (accept state)
        assert productive == {"q0", "q1", "q2"}

    def test_find_productive_some_non_productive(self):
        """Test finding productive states with non-productive states."""
        dfa = DFA(
            states=["q0", "q1", "q_trap"],
            alphabet=["a", "b"],
            transitions={
                "q0": {"a": "q1", "b": "q_trap"},
                "q1": {"a": "q1", "b": "q1"},
                "q_trap": {"a": "q_trap", "b": "q_trap"}
            },
            start_state="q0",
            accept_states=["q1"]
        )

        productive = self.optimizer.find_productive_states(dfa)
        # q_trap cannot reach accept state
        assert productive == {"q0", "q1"}
        assert "q_trap" not in productive

    def test_find_productive_no_accept_states(self):
        """Test finding productive states with no accept states."""
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["a", "b"],
            transitions={
                "q0": {"a": "q1", "b": "q0"},
                "q1": {"a": "q1", "b": "q1"}
            },
            start_state="q0",
            accept_states=[]
        )

        productive = self.optimizer.find_productive_states(dfa)
        # No accept states means no productive states
        assert productive == set()

    # ==================== CLEANUP TESTS ====================

    def test_cleanup_removes_unreachable(self):
        """Test that cleanup removes unreachable states."""
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

        cleaned = self.optimizer.cleanup(dfa)

        assert "q_unreachable" not in cleaned.states
        assert "q0" in cleaned.states
        assert "q1" in cleaned.states

    def test_cleanup_preserves_language(self):
        """Test that cleanup preserves the language."""
        dfa = DFA(
            states=["q0", "q1", "q2", "q_unreachable"],
            alphabet=["a", "b"],
            transitions={
                "q0": {"a": "q1", "b": "q2"},
                "q1": {"a": "q1", "b": "q1"},
                "q2": {"a": "q2", "b": "q2"},
                "q_unreachable": {"a": "q_unreachable", "b": "q_unreachable"}
            },
            start_state="q0",
            accept_states=["q1"]
        )

        cleaned = self.optimizer.cleanup(dfa)

        # Test strings should have same acceptance
        test_strings = ["", "a", "b", "aa", "ab", "ba", "bb", "aaa", "aab"]
        for s in test_strings:
            assert simulate_dfa(cleaned, s) == simulate_dfa(dfa, s), f"Failed for string: {s}"

    def test_cleanup_single_state_accept(self):
        """Test cleanup of single accept state DFA."""
        dfa = DFA(
            states=["q0"],
            alphabet=["a", "b"],
            transitions={
                "q0": {"a": "q0", "b": "q0"}
            },
            start_state="q0",
            accept_states=["q0"]
        )

        cleaned = self.optimizer.cleanup(dfa)
        assert len(cleaned.states) == 1
        assert simulate_dfa(cleaned, "") is True
        assert simulate_dfa(cleaned, "a") is True
        assert simulate_dfa(cleaned, "ab") is True

    def test_cleanup_single_state_reject(self):
        """Test cleanup of single reject state DFA."""
        dfa = DFA(
            states=["q0"],
            alphabet=["a", "b"],
            transitions={
                "q0": {"a": "q0", "b": "q0"}
            },
            start_state="q0",
            accept_states=[]
        )

        cleaned = self.optimizer.cleanup(dfa)
        assert len(cleaned.states) == 1
        assert simulate_dfa(cleaned, "") is False
        assert simulate_dfa(cleaned, "a") is False
        assert simulate_dfa(cleaned, "ab") is False

    # ==================== VERBOSE MODE TESTS ====================

    def test_verbose_mode(self):
        """Test verbose mode logging."""
        optimizer_verbose = DFAOptimizer(verbose=True)
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["a"],
            transitions={"q0": {"a": "q1"}, "q1": {"a": "q1"}},
            start_state="q0",
            accept_states=["q1"]
        )

        # Should not raise
        result = optimizer_verbose.cleanup(dfa)
        assert result is not None

    def test_get_optimization_report(self):
        """Test optimization report generation."""
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

        cleaned = self.optimizer.cleanup(dfa)
        report = self.optimizer.get_optimization_report(dfa, cleaned)
        
        assert isinstance(report, dict)
