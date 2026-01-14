Commit Record (History)
This document records the sequence of notable commits and feature changes for the repository.
Each entry contains: Commit: <Title>, Author, Date (YYYY-MM-DD), and a short summary of changes.

---

Commit: Init — Project scaffold and basic DFA pipeline
Author: Iswar patra
Date: 2024-01-04
Summary:
- Initial project scaffold: frontend (React/Vite) + backend (python_imply).
- Added placeholder Analyst/Architect/Validator agents and README skeleton.

---

Commit: Feature: Basic DFA builders and LLM stubs
Author: Iswar patra
Date: 2024-01-04
Summary:
- Implemented atomic DFA templates for STARTS_WITH / ENDS_WITH / CONTAINS.
- Added BaseAgent.call_ollama stub for LLM integration.
- Added simple API endpoint /generate (FastAPI).

---

Commit: Fix: Validator refactor to deterministic engine
Author: Iswar patra
Date: 2023-12-03
Summary:
- Replaced ad-hoc validation with DeterministicValidator class.
- Added simulation-based tests for basic atomic logic types.

---

Commit: Feature: Auto-Repair engine (initial)
Author: Iswar patra
Date: 2023-12-28
Summary:
- Added DFARepairEngine skeleton and simple chain repair heuristics.
- Added CLI script for local visualizer and debug runs.

---

Commit: Test: Add unit tests for core logic
Author: Iswar patra
Date: 2023-12-15
Summary:
- Added test_core_logic.py with tests for STARTS_WITH, ENDS_WITH, CONTAINS, NOT_* behaviours.
- Achieved basic test coverage for atomic validators.

---

Commit: Enhancement: multi-character target chain handling
Author: Iswar patra
Date: 2023-12-10
Summary:
- Improved chain-builder to create states for multi-character targets (e.g., "bb", "aba").
- Hardened transition repair to avoid hallucinated symbols.

---

Commit: Feature: DFA inversion and dead-state handling
Author: Iswar patra
Date: 2023-12-04
Summary:
- Implemented invert_dfa to compute complement DFAs.
- Added dead/trap state handling to ensure total transition functions.

---

Commit: Improvement: visualizer and Graphviz integration
Author: Iswar patra
Date: 2023-12-17
Summary:
- Visualizer tool improved: better node/edge labeling, safe filename generation.
- Added Graphviz detection and graceful fallback.

---

Commit: Fix: DeterministicValidator edge-case handling
Author: Iswar patra
Date: 2023-12-17
Summary:
- Fixed edge cases in get_truth (DIVISIBLE_BY mapping and NO_CONSECUTIVE).
- Added safety checks for invalid alphabet characters during simulation.

---

Commit: Enhancement: Frontend samples and UX polish
Author: Iswar patra
Date: 2023-12-24
Summary:
- Added example prompts, improved textarea shortcuts, error handling for backend failures.

---

Commit: Feature: Product construction engine (product automaton)
Author: Iswar patra
Date: 2023-12-24
Summary:
- Added ProductConstructionEngine skeleton to combine DFAs (AND/OR) and invert DFAs.
- ArchitectAgent updated to call product engine for composition.

---

Commit: Fix: Heuristic parser improvements (atomic detection)
Author: Iswar patra
Date: 2023-12-28
Summary:
- Improved simple regex heuristics to extract targets from quoted/unquoted text.
- Better alphabet deduction for 'a'/'b' vs '0'/'1'.

---

Commit: Feature: CLI and lifecycle hooks
Author: Iswar patra
Date: 2024-01-04
Summary:
- Added CLI arguments to main (model selection, max_product_states).
- Lifecycle startup/shutdown logging improved.

---

Commit: Feature: Conservative LLM fallback templates
Author: Iswar patra
Date: 2023-12-28
Summary:
- Strengthened system prompts for AnalystAgent to reduce LLM hallucination (explicit JSON schema).
- Added DFA-detection guard when LLM returns DFA instead of logic spec.

---

Commit: Enhancement: Repair engine robustness (chain builder)
Author: Iswar patra
Date: 2023-12-28
Summary:
- Hardening of auto_repair_dfa: reachability checks, dead-state elimination, alphabet lockdown.

---

Commit: Improvement: Deterministic tests expanded & documentation
Author: Iswar patra
Date: 2024-01-19
Summary:
- Expanded unit tests to cover multi-character patterns and some composite flows.
- README updated with usage examples.

---

Commit: Refactor: split python_imply into modular agents
Author: Iswar patra
Date: 2023-12-17
Summary:
- Modularized agents into core/ (analyst, architect, validator) and engines (product, repair).
- Improved Pydantic models for DFA and LogicSpec.

---

Commit: Feature: Initial support for numeric constraints (DIVISIBLE_BY)
Author: Iswar patra
Date: 2023-12-10
Summary:
- Added DIVISIBLE_BY logic parsing and validator handling with conservative mapping (binary, decimal).
- Added tests for divisibility in binary strings.

---

Commit: Fix: Edge-case DIVISIBLE_BY mapping and parse safety
Author: Iswar patra
Date: 2023-12-17
Summary:
- Avoided incorrect numeric mapping for non-digit alphabets.
- Validator now returns False for unsupported alphabets rather than raise.

---

Commit: Feature: Local composite parsing (fast path for AND/OR chains)
Author: Iswar patra
Date: 2024-01-19
Summary:
- Added a fast local splitter to detect top-level "A and B and C" and "A or B or C" where possible.
- Falls back to LLM when local parsing is insufficient.

---

Commit: Feature: Alphabet unification and N-ary combine + safety checks
Author: Iswar patra
Date: 2024-01-19
Summary:
- Added alphabet-unification heuristics across composite LogicSpec children.
- Implemented flattening of nested AND/OR to N-ary children.
- Added product-size estimator and max_product_states safety threshold to prevent blow-ups.

---

Commit: Feature: Deterministic builders for length/count/product parity
Author: Iswar patra
Date: 2023-12-10
Summary:
- Added deterministic DFA builders for EXACT_LENGTH, MIN_LENGTH, MAX_LENGTH, LENGTH_MOD, COUNT_MOD, PRODUCT_EVEN.
- Updated ArchitectAgent to prefer in-code builders before LLM DFA generation.

---

Commit: Chore: Pydantic V2 migration (models) and warning cleanup
Author: Iswar patra
Date: 2023-12-17
Summary:
- Migrated core models to Pydantic V2 style (ConfigDict/model_validator).
- Removed update_forward_refs and replaced with future annotations on models.
- Reduced deprecation warnings in test runs.

---

Commit: Feature: Full composition integration, tests, and docs updates
Author: Iswar patra
Date: 2024-01-19
Summary:
- Completed integration of alphabet unification, N-ary AND/OR composition, product-size pre-checks, and conservative NL parsing.
- Added comprehensive tests (test_core_logic_extra.py) covering string patterns, numeric constraints, length/count checks, and product parity.
- Updated README and commit.md to document new NL forms, mapping rules, and CLI options.
- Default max_product_states set to 2000 (configurable via AUTO_DFA_MAX_PRODUCT_STATES).
- Committed by: Iswar patra

---

Notes
- This file is a curated activity log; additional small commits and refactors exist in the repository history that are not listed here for brevity.
- If you'd like, I can expand each entry with explicit file lists and diff summaries (per-commit file changes), or convert this into a full chronological git-style changelog with commit SHAs.
