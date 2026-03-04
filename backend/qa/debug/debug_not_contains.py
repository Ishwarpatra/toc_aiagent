#!/usr/bin/env python3
"""Debug script to trace NOT_CONTAINS logic"""

import sys
sys.path.insert(0, '../src')

from core.models import LogicSpec, DFA
from core.agents import ArchitectAgent, build_substring_dfa

# Test case: "doesn't contain '1'"
pattern = "1"
alphabet = ['0', '1']

print("=" * 60)
print(f"DEBUG: NOT_CONTAINS '{pattern}' over alphabet {alphabet}")
print("=" * 60)

# Step 1: Build CONTAINS DFA
print("\n[Step 1] Building CONTAINS DFA...")
contains_dict = build_substring_dfa(alphabet, pattern)
print(f"  States: {contains_dict['states']}")
print(f"  Accept: {contains_dict['accept_states']}")
print(f"  Transitions:")
for s, trans in contains_dict['transitions'].items():
    print(f"    {s}: {trans}")

contains_dfa = DFA(**contains_dict)

# Step 2: Test CONTAINS
print("\n[Step 2] Testing CONTAINS DFA...")
test_strs = ['0', '00', '000', '1', '01', '11']
for s in test_strs:
    result = contains_dfa.accepts(s)
    expected = pattern in s
    status = "OK" if result == expected else "WRONG"
    print(f"  '{s}' -> {result} (expected {expected}) [{status}]")

# Step 3: Invert via product engine
print("\n[Step 3] Inverting DFA via ProductConstructionEngine...")
from core.product import ProductConstructionEngine
pe = ProductConstructionEngine()
not_contains_dfa = pe.invert(contains_dfa)

print(f"  States: {not_contains_dfa.states}")
print(f"  Accept: {not_contains_dfa.accept_states}")
print(f"  Transitions:")
for s, trans in not_contains_dfa.transitions.items():
    print(f"    {s}: {trans}")

# Step 4: Test NOT_CONTAINS
print("\n[Step 4] Testing NOT_CONTAINS DFA...")
for s in test_strs:
    result = not_contains_dfa.accepts(s)
    expected = pattern not in s
    status = "OK" if result == expected else "WRONG"
    print(f"  '{s}' -> {result} (expected {expected}) [{status}]")

print("\n" + "=" * 60)
