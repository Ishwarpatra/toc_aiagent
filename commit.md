Commit Record

Commit: Refactor: Replace AI Validator with Deterministic Engine

Author: Iswar patra

Date: Dec 3, 2025

Summary

Refactored the validation architecture to replace the LLM-based "Agent 3" with a pure Python deterministic engine (validator.py). This eliminates hallucinations where the validator would incorrectly flag valid DFAs. Additionally, the Auto-Repair engine has been significantly hardened to handle multi-character patterns (e.g., "starts with bb") and prevent graph corruption.

 Key Architectural Changes

1. New Validator Engine (validator.py)

Removed: Regex-based guessing inside main.py.

Added: A standalone DeterministicValidator class.

Logic: Implemented strict boolean checks for:

STARTS_WITH / NOT_STARTS_WITH

ENDS_WITH / NOT_ENDS_WITH

CONTAINS / NOT_CONTAINS

Testing: Added test_core_logic.py with 100% Pytest coverage to ensure the ground truth never lies.

2. Structured Agent 1 (The Parser)

Old Behavior: Agent 1 outputted free text summaries.

New Behavior: Agent 1 outputs a strict LogicSpec JSON object (e.g., {"logic_type": "STARTS_WITH", "target": "bb"}).

Benefit: Provides exact variables needed for the deterministic chain builder.

3. "Scorched Earth" Auto-Repair

The Auto-Repair engine in main.py received three critical upgrades:

Chain Builder: Constructs full state chains for targets longer than 1 character (e.g., q0 -> q1 -> q2 for "bb").

Alphabet Lockdown: Forces the alphabet to ['a', 'b'] and actively deletes hallucinated transitions (e.g., c, d).

Start State Enforcement: Hard-overwrites any transitions leaving the start state to ensure immediate rejection of invalid inputs.

4. Verification

Unit Tests: Passed (6/6 scenarios covered) in test_core_logic.py.

End-to-End Tests: Validated against "starts with b", "starts with bb", and "contains aba".

Visuals: Graphs are now clean, deterministic, and free of hallucinated edges.

Commit: Feature: Add DFA Inversion, Optimization, and Robustness Fixes

Author: Iswar patra

Date: Dec 4, 2025

Summary

This update introduces new theoretical operations and performance monitoring tools while addressing critical stability issues in the random generation and repair pipelines. The system can now generate the complement of a language and automatically handle dead state edge cases during repair, ensuring smoother execution for complex automata.

Key Architectural Changes

New Feature: DFA Inversion (invert_dfa)

Added: Implemented the invert_dfa function to construct the complement of a DFA.

Logic: Swaps accepting states with non-accepting states while preserving existing transitions.

Utility: Essential for verifying negative constraints by inverting the positive case logic.

Performance Monitoring

Added: A custom execution_timer decorator to track performance.

Usage: Wrapped computationally heavy functions like simulation and auto-repair to track execution time.

Benefit: Allows for profiling the Architect and Validator phases to identify specific bottlenecks.

Fix: Random DFA Generation

Issue: Previous logic occasionally created disconnected graphs or invalid transition maps.

Resolution: Enforced reachability checks from the start state and ensured every state has a complete set of transitions for the alphabet.

Enhancement: Auto-Repair Dead States

Context: The auto-repair function previously failed when encountering trap scenarios.

Improvement: Explicitly detects missing transitions and routes them to a designated q_dead state, treating it as a non-accepting sink that loops on all inputs.

Verification

Unit Tests: Added tests for invert_dfa ensuring the complement logic holds true.

Regression: Confirmed auto_repair_dfa no longer throws errors on partial transition tables.

End-to-End Tests: Validated that dead states are correctly attached during the repair process.

Visuals: Graphs correctly display trap states when necessary.