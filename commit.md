Commit Description: Deterministic Validator & Auto-Repair Overhaul

🚀 Summary

Refactored the validation architecture to replace the LLM-based "Agent 3" with a pure Python deterministic engine (validator.py). This eliminates hallucinations where the validator would incorrectly flag valid DFAs. Additionally, the Auto-Repair engine has been significantly hardened to handle multi-character patterns (e.g., "starts with bb") and prevent graph corruption ("spaghetti graphs").

🛠 Key Architectural Changes

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

Benefit: This provides the exact variables needed for the deterministic chain builder.

3. "Scorched Earth" Auto-Repair

The Auto-Repair engine in main.py received three critical upgrades:

Chain Builder: Instead of patching single transitions, it now constructs full state chains for targets longer than 1 character (e.g., q0 -> q1 -> q2 for "bb").

Alphabet Lockdown: Forces the alphabet to ['a', 'b'] and actively deletes hallucinated transitions (e.g., c, d) to prevent messy visualizations.

Start State Enforcement: Hard-overwrites any transitions leaving the start state to ensure immediate rejection of invalid inputs.

Verification

Unit Tests: Passed (6/6 scenarios covered).

End-to-End Tests: Validated against "starts with b", "starts with bb", and "contains aba".

Visuals: Graphs are now clean, deterministic, and free of hallucinated edges.