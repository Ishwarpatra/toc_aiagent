#!/usr/bin/env python3
"""
Debug Repair Unit Tests for Auto-DFA

This module contains unit tests for the DFA repair engine and the new DFA
simulation methods. It tests the logic independently of LLM responses using
deterministic mock data.

Usage:
    python -m pytest scripts/debug_repair.py -v
    
    Or run directly:
    python scripts/debug_repair.py
"""

import json
import sys
import os
import unittest
from pathlib import Path

# Add backend to path properly using Path
SCRIPT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = SCRIPT_DIR.parent
SRC_DIR = BACKEND_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from core.models import DFA, LogicSpec


class TestDFAAcceptsMethod(unittest.TestCase):
    """Unit tests for the DFA.accepts() method - core of Black Box testing."""
    
    def test_simple_starts_with_0(self):
        """Test a DFA that accepts strings starting with '0'."""
        dfa = DFA(
            states=["q0", "q1", "qF"],
            alphabet=["0", "1"],
            start_state="q0",
            accept_states=["q1"],
            transitions={
                "q0": {"0": "q1", "1": "qF"},
                "q1": {"0": "q1", "1": "q1"},
                "qF": {"0": "qF", "1": "qF"}
            }
        )
        
        # Black Box tests
        self.assertTrue(dfa.accepts("0"))
        self.assertTrue(dfa.accepts("00"))
        self.assertTrue(dfa.accepts("01"))
        self.assertTrue(dfa.accepts("010101"))
        
        self.assertFalse(dfa.accepts("1"))
        self.assertFalse(dfa.accepts("10"))
        self.assertFalse(dfa.accepts("11"))
        self.assertFalse(dfa.accepts(""))  # q0 is not accept state
    
    def test_starts_with_ab(self):
        """Test a DFA that accepts strings starting with 'ab'."""
        dfa = DFA(
            states=["q0", "q1", "q2", "qF"],
            alphabet=["a", "b"],
            start_state="q0",
            accept_states=["q2"],
            transitions={
                "q0": {"a": "q1", "b": "qF"},
                "q1": {"a": "qF", "b": "q2"},
                "q2": {"a": "q2", "b": "q2"},
                "qF": {"a": "qF", "b": "qF"}
            }
        )
        
        self.assertTrue(dfa.accepts("ab"))
        self.assertTrue(dfa.accepts("aba"))
        self.assertTrue(dfa.accepts("abb"))
        self.assertTrue(dfa.accepts("abab"))
        
        self.assertFalse(dfa.accepts("a"))
        self.assertFalse(dfa.accepts("ba"))
        self.assertFalse(dfa.accepts("b"))
        self.assertFalse(dfa.accepts(""))
        self.assertFalse(dfa.accepts("aab"))
    
    def test_ends_with_01(self):
        """Test a DFA that accepts strings ending with '01'."""
        dfa = DFA(
            states=["q0", "q1", "q2"],
            alphabet=["0", "1"],
            start_state="q0",
            accept_states=["q2"],
            transitions={
                "q0": {"0": "q1", "1": "q0"},
                "q1": {"0": "q1", "1": "q2"},
                "q2": {"0": "q1", "1": "q0"}
            }
        )
        
        self.assertTrue(dfa.accepts("01"))
        self.assertTrue(dfa.accepts("001"))
        self.assertTrue(dfa.accepts("101"))
        self.assertTrue(dfa.accepts("0101"))
        
        self.assertFalse(dfa.accepts("0"))
        self.assertFalse(dfa.accepts("1"))
        self.assertFalse(dfa.accepts("10"))
        self.assertFalse(dfa.accepts("00"))
        self.assertFalse(dfa.accepts("11"))
    
    def test_contains_11(self):
        """Test a DFA that accepts strings containing '11'."""
        dfa = DFA(
            states=["q0", "q1", "q2"],
            alphabet=["0", "1"],
            start_state="q0",
            accept_states=["q2"],
            transitions={
                "q0": {"0": "q0", "1": "q1"},
                "q1": {"0": "q0", "1": "q2"},
                "q2": {"0": "q2", "1": "q2"}
            }
        )
        
        self.assertTrue(dfa.accepts("11"))
        self.assertTrue(dfa.accepts("011"))
        self.assertTrue(dfa.accepts("110"))
        self.assertTrue(dfa.accepts("111"))
        self.assertTrue(dfa.accepts("0110"))
        
        self.assertFalse(dfa.accepts(""))
        self.assertFalse(dfa.accepts("0"))
        self.assertFalse(dfa.accepts("1"))
        self.assertFalse(dfa.accepts("01"))
        self.assertFalse(dfa.accepts("10"))
        self.assertFalse(dfa.accepts("01010"))
    
    def test_even_number_of_1s(self):
        """Test a DFA that accepts strings with even number of 1s."""
        dfa = DFA(
            states=["even", "odd"],
            alphabet=["0", "1"],
            start_state="even",
            accept_states=["even"],
            transitions={
                "even": {"0": "even", "1": "odd"},
                "odd": {"0": "odd", "1": "even"}
            }
        )
        
        self.assertTrue(dfa.accepts(""))  # 0 ones (even)
        self.assertTrue(dfa.accepts("0"))  # 0 ones
        self.assertTrue(dfa.accepts("00"))  # 0 ones
        self.assertTrue(dfa.accepts("11"))  # 2 ones
        self.assertTrue(dfa.accepts("0110"))  # 2 ones
        self.assertTrue(dfa.accepts("1111"))  # 4 ones
        
        self.assertFalse(dfa.accepts("1"))  # 1 one (odd)
        self.assertFalse(dfa.accepts("01"))  # 1 one
        self.assertFalse(dfa.accepts("10"))  # 1 one
        self.assertFalse(dfa.accepts("111"))  # 3 ones
    
    def test_invalid_characters_reject(self):
        """Test that strings with characters not in alphabet are rejected."""
        dfa = DFA(
            states=["q0"],
            alphabet=["0", "1"],
            start_state="q0",
            accept_states=["q0"],
            transitions={
                "q0": {"0": "q0", "1": "q0"}
            }
        )
        
        self.assertFalse(dfa.accepts("a"))
        self.assertFalse(dfa.accepts("0a1"))
        self.assertFalse(dfa.accepts("x"))
    
    def test_missing_transitions_crash(self):
        """Test that missing transitions cause rejection (crash)."""
        # Incomplete DFA - missing transition for '1' from q1
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            start_state="q0",
            accept_states=["q1"],
            transitions={
                "q0": {"0": "q1", "1": "q0"},
                "q1": {"0": "q1"}  # Missing "1" transition
            }
        )
        
        self.assertTrue(dfa.accepts("0"))  # OK
        self.assertTrue(dfa.accepts("00"))  # OK
        self.assertFalse(dfa.accepts("01"))  # Crashes - no transition for '1' from q1


class TestDFASimulateWithTrace(unittest.TestCase):
    """Unit tests for the DFA.simulate_with_trace() debugging method."""
    
    def test_successful_trace(self):
        """Test trace for an accepted string."""
        dfa = DFA(
            states=["q0", "q1", "q2"],
            alphabet=["a", "b"],
            start_state="q0",
            accept_states=["q2"],
            transitions={
                "q0": {"a": "q1", "b": "q0"},
                "q1": {"a": "q1", "b": "q2"},
                "q2": {"a": "q2", "b": "q2"}
            }
        )
        
        result = dfa.simulate_with_trace("ab")
        
        self.assertTrue(result["accepted"])
        self.assertEqual(result["final_state"], "q2")
        self.assertIsNone(result["crash_reason"])
        self.assertEqual(len(result["trace"]), 2)
        self.assertEqual(result["trace"][0], ("q0", "a", "q1"))
        self.assertEqual(result["trace"][1], ("q1", "b", "q2"))
    
    def test_rejected_trace(self):
        """Test trace for a rejected string."""
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            start_state="q0",
            accept_states=["q1"],
            transitions={
                "q0": {"0": "q1", "1": "q0"},
                "q1": {"0": "q1", "1": "q1"}
            }
        )
        
        result = dfa.simulate_with_trace("11")
        
        self.assertFalse(result["accepted"])
        self.assertEqual(result["final_state"], "q0")  # Ended in non-accept state
        self.assertIsNone(result["crash_reason"])
    
    def test_crash_on_invalid_char(self):
        """Test trace when encountering invalid character."""
        dfa = DFA(
            states=["q0"],
            alphabet=["0", "1"],
            start_state="q0",
            accept_states=["q0"],
            transitions={
                "q0": {"0": "q0", "1": "q0"}
            }
        )
        
        result = dfa.simulate_with_trace("0a1")
        
        self.assertFalse(result["accepted"])
        self.assertIsNone(result["final_state"])
        self.assertIn("Invalid character", result["crash_reason"])
        self.assertEqual(len(result["trace"]), 1)  # Only '0' was processed
    
    def test_empty_string(self):
        """Test trace for empty string."""
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            start_state="q0",
            accept_states=["q0"],
            transitions={
                "q0": {"0": "q1", "1": "q1"},
                "q1": {"0": "q0", "1": "q0"}
            }
        )
        
        result = dfa.simulate_with_trace("")
        
        self.assertTrue(result["accepted"])  # q0 is accept state
        self.assertEqual(result["final_state"], "q0")
        self.assertEqual(len(result["trace"]), 0)  # No transitions


class TestDFAModelDump(unittest.TestCase):
    """Unit tests for DFA model_dump method."""
    
    def test_model_dump_structure(self):
        """Test that model_dump returns expected structure."""
        dfa = DFA(
            states=["q0", "q1"],
            alphabet=["0", "1"],
            start_state="q0",
            accept_states=["q1"],
            transitions={"q0": {"0": "q1", "1": "q0"}, "q1": {"0": "q1", "1": "q1"}},
            reasoning="Test DFA"
        )
        
        dump = dfa.model_dump()
        
        self.assertIn("states", dump)
        self.assertIn("alphabet", dump)
        self.assertIn("start_state", dump)
        self.assertIn("accept_states", dump)
        self.assertIn("transitions", dump)
        self.assertIn("reasoning", dump)
        
        self.assertEqual(dump["states"], ["q0", "q1"])
        self.assertEqual(dump["start_state"], "q0")
        self.assertEqual(dump["reasoning"], "Test DFA")


class TestLogicSpecFromPrompt(unittest.TestCase):
    """Unit tests for LogicSpec.from_prompt() atomic parsing."""
    
    def test_starts_with_pattern(self):
        """Test parsing 'starts with' prompts."""
        spec = LogicSpec.from_prompt("starts with 'ab'")
        self.assertEqual(spec.logic_type, "STARTS_WITH")
        self.assertEqual(spec.target, "ab")
    
    def test_ends_with_pattern(self):
        """Test parsing 'ends with' prompts."""
        spec = LogicSpec.from_prompt("ends with '01'")
        self.assertEqual(spec.logic_type, "ENDS_WITH")
        self.assertEqual(spec.target, "01")
    
    def test_contains_pattern(self):
        """Test parsing 'contains' prompts."""
        spec = LogicSpec.from_prompt("contains '11'")
        self.assertEqual(spec.logic_type, "CONTAINS")
        self.assertEqual(spec.target, "11")
    
    def test_divisible_by(self):
        """Test parsing 'divisible by' prompts."""
        spec = LogicSpec.from_prompt("divisible by 3")
        self.assertEqual(spec.logic_type, "DIVISIBLE_BY")
        self.assertEqual(spec.target, "3")
    
    def test_even_count(self):
        """Test parsing 'even number of' prompts."""
        spec = LogicSpec.from_prompt("even number of 1s")
        self.assertEqual(spec.logic_type, "EVEN_COUNT")


def run_manual_debug():
    """Run manual debug output for visual inspection."""
    print("\n" + "=" * 60)
    print("  DFA SIMULATION DEBUG OUTPUT")
    print("=" * 60 + "\n")
    
    # Test case 1: Starts with '0'
    print("[Test 1] DFA: Starts with '0'")
    dfa = DFA(
        states=["q0", "q1", "qF"],
        alphabet=["0", "1"],
        start_state="q0",
        accept_states=["q1"],
        transitions={
            "q0": {"0": "q1", "1": "qF"},
            "q1": {"0": "q1", "1": "q1"},
            "qF": {"0": "qF", "1": "qF"}
        }
    )
    
    print(f"  States: {dfa.states}")
    print(f"  Alphabet: {dfa.alphabet}")
    print(f"  Start: {dfa.start_state}")
    print(f"  Accept: {dfa.accept_states}")
    
    print("\n  Black Box Tests:")
    test_strings = ["0", "00", "01", "1", "10", "11", ""]
    for s in test_strings:
        result = dfa.accepts(s)
        expected = s.startswith("0") if s else False
        status = "✓" if result == expected else "✗"
        print(f"    {status} accepts('{s}') = {result} (expected: {expected})")
    
    # Test case 2: Trace demonstration
    print("\n" + "-" * 60)
    print("[Test 2] Trace demonstration")
    trace_result = dfa.simulate_with_trace("010")
    print(f"  Input: '010'")
    print(f"  Accepted: {trace_result['accepted']}")
    print(f"  Final State: {trace_result['final_state']}")
    print(f"  Trace:")
    for step in trace_result["trace"]:
        print(f"    {step[0]} --{step[1]}--> {step[2]}")
    
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Run manual debug output")
    args = parser.parse_args()
    
    if args.debug:
        run_manual_debug()
    else:
        # Run unit tests
        unittest.main(argv=[''], exit=False, verbosity=2)
