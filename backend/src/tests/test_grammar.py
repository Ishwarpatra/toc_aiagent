"""
Unit tests for GrammarBuilder in core/grammar.py.

Verifies DFA to Right-Linear Regular Grammar mathematical properties:
- Correct variable mapping (Start state -> S, others -> A, B, ...)
- Transition productions (S -> aA, etc.)
- Accept state epsilon productions (Vk -> "")
- Start state as accept state (ε in language)
- Multiple states and complex topologies
- Grammar formatting output
"""

import unittest
from core.models import DFA
from core.grammar import GrammarBuilder


class TestGrammarBuilder(unittest.TestCase):
    def test_dfa_to_grammar_binary_ending_in_one(self):
        """
        DFA accepts binary strings ending in '1'.
        q0 --0--> q0, q0 --1--> q1
        q1 --0--> q0, q1 --1--> q1
        Start: q0, Accept: q1
        """
        dfa = DFA(
            states={"q0", "q1"},
            alphabet={"0", "1"},
            transitions={
                "q0": {"0": "q0", "1": "q1"},
                "q1": {"0": "q0", "1": "q1"}
            },
            start_state="q0",
            accept_states={"q1"}
        )

        grammar = GrammarBuilder.build_from_dfa(dfa)

        # q0 maps to S, q1 maps to A
        self.assertIn("0S", grammar["S"])
        self.assertIn("1A", grammar["S"])
        self.assertNotIn("", grammar["S"])

        self.assertIn("0S", grammar["A"])
        self.assertIn("1A", grammar["A"])
        self.assertIn("", grammar["A"])  # Accept state has epsilon

    def test_dfa_to_grammar_accept_start_state(self):
        """
        DFA accepts strings with even length (start state is accept state).
        """
        dfa = DFA(
            states={"q0", "q1"},
            alphabet={"a"},
            transitions={
                "q0": {"a": "q1"},
                "q1": {"a": "q0"}
            },
            start_state="q0",
            accept_states={"q0"}
        )

        grammar = GrammarBuilder.build_from_dfa(dfa)

        # S is accept state -> S -> ε
        self.assertIn("", grammar["S"])
        self.assertIn("aA", grammar["S"])
        self.assertIn("aS", grammar["A"])
        self.assertNotIn("", grammar["A"])

    def test_dfa_to_grammar_multiple_accept_states(self):
        """
        DFA with multiple accept states.
        """
        dfa = DFA(
            states={"q0", "q1", "q2"},
            alphabet={"0", "1"},
            transitions={
                "q0": {"0": "q1", "1": "q2"},
                "q1": {"0": "q1", "1": "q1"},
                "q2": {"0": "q2", "1": "q2"}
            },
            start_state="q0",
            accept_states={"q1", "q2"}
        )

        grammar = GrammarBuilder.build_from_dfa(dfa)

        self.assertEqual(len(grammar), 3)
        self.assertIn("S", grammar)
        self.assertIn("A", grammar)
        self.assertIn("B", grammar)

        # Both A and B should produce epsilon
        self.assertIn("", grammar["A"])
        self.assertIn("", grammar["B"])
        self.assertNotIn("", grammar["S"])

    def test_format_grammar(self):
        grammar = {
            "S": ["0S", "1A"],
            "A": ["0S", "1A", ""]
        }
        formatted = GrammarBuilder.format_grammar(grammar, start_symbol="S")
        self.assertIn("Start symbol: S", formatted)
        self.assertIn("Productions:", formatted)
        self.assertIn("S -> 0S | 1A", formatted)
        self.assertIn("A -> 0S | 1A | ε", formatted)

    def test_empty_language_dfa(self):
        """
        DFA with no accept states produces no epsilon productions.
        """
        dfa = DFA(
            states={"q0"},
            alphabet={"0", "1"},
            transitions={"q0": {"0": "q0", "1": "q0"}},
            start_state="q0",
            accept_states=[]
        )

        grammar = GrammarBuilder.build_from_dfa(dfa)
        self.assertNotIn("", grammar["S"])
        self.assertIn("0S", grammar["S"])
        self.assertIn("1S", grammar["S"])


if __name__ == "__main__":
    unittest.main()
