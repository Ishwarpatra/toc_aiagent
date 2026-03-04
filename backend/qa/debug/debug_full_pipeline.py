#!/usr/bin/env python3
"""Debug script to trace full pipeline for 'doesn't contain 1' prompt"""

import sys
sys.path.insert(0, '../src')

from core.models import LogicSpec, DFA
from core.agents import ArchitectAgent, AnalystAgent

# Test case: use command line arg if provided, else default
prompt = sys.argv[1] if len(sys.argv) > 1 else "doesn't contain '1'"

print("=" * 60)
print(f"DEBUG: Full pipeline for prompt: '{prompt}'")
print("=" * 60)

# Step 1: Analyst parses the prompt
print("\n[Step 1] Analyst parsing prompt...")
analyst = AnalystAgent(model_name="local")
spec = analyst.analyze(prompt)
print(f"  LogicSpec:")
print(f"    logic_type: {spec.logic_type}")
print(f"    target: {spec.target}")
print(f"    alphabet: {spec.alphabet}")

import random

# Step 2: Architect builds DFA
print("\n[Step 2] Architect building DFA...", flush=True)
architect = ArchitectAgent(model_name="local")
dfa = architect.design(spec)
print(f"  DFA Built: {dfa.reasoning}", flush=True)

# Step 3: Test the DFA
print("\n[Step 3] Testing DFA against oracle strings...", flush=True)
from generate_tests import get_oracle_strings
op_type = dfa.reasoning.split(' ')[0] if dfa.reasoning else spec.logic_type
test_accept, test_reject = get_oracle_strings(op_type, spec.target, dfa.alphabet)

# If get_oracle_strings fails, try to infer
if not test_accept and not test_reject:
    print("  [Warning] get_oracle_strings returned nothing, using random generation...")
    from generate_tests import check_condition
    # Try some random strings
    for _ in range(500):
        s = "".join(random.choice(dfa.alphabet) for _ in range(random.randint(0, 15)))
        if check_condition(s, spec.logic_type, spec.target, dfa.alphabet):
            if len(test_accept) < 5: test_accept.append(s)
        else:
            if len(test_reject) < 5: test_reject.append(s)

print(f"  Oracle Accept: {test_accept}")
print(f"  Oracle Reject: {test_reject}")

print("\n  Validation Results:")
for s in test_accept:
    result = dfa.accepts(s)
    status = "OK" if result else "WRONG - REJECTED!"
    print(f"    '{s}' -> {result} [{status}]")

for s in test_reject:
    result = dfa.accepts(s)
    status = "OK" if not result else "WRONG - ACCEPTED!"
    print(f"    '{s}' -> {result} [{status}]")

print("\n" + "=" * 60)
