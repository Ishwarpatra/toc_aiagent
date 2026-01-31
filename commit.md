Commit Record (History)
This document records the sequence of notable commits and feature changes for the repository.
Each entry contains: Commit: <Title>, Author, Date (YYYY-MM-DD), and a short summary of changes.

---

Commit: Refactor: Replace AI Validator with Deterministic Engine
Author: Ishwarpatra
Date: 2025-12-03
Summary:
- Replaced ad-hoc AI-based validation with DeterministicValidator class.
- Added simulation-based tests for basic atomic logic types.
- Fixed edge-case numeric mapping (DIVISIBLE_BY) and parse safety.
- Validator now returns False for unsupported alphabets rather than raising exceptions.

---

Commit: feat: add inversion logic and timer, fix DFA generation
Author: Ishwarpatra
Date: 2025-12-04
Summary:
- Implemented `invert_dfa` to compute complement DFAs.
- Added dead/trap state handling to ensure total transition functions.
- Added timer for DFA generation performance tracking.
- Initial creation of `commit.md` for record tracking.

---

Commit: feat: add support for advanced DFA logic patterns (math/parity/consecutive)
Author: Ishwarpatra
Date: 2025-12-10
Summary:
- Added deterministic DFA builders for EXACT_LENGTH, MIN_LENGTH, MAX_LENGTH, LENGTH_MOD, COUNT_MOD, PRODUCT_EVEN.
- Improved chain-builder to create states for multi-character targets (e.g., "bb", "aba").
- Initial support for numeric constraints (DIVISIBLE_BY) with binary/decimal mapping.
- Hardened transition repair to avoid hallucinated symbols.

---

Commit: feat: added test for agent_1
Author: SpyBroker
Date: 2025-12-13
Summary:
- Added unit tests for `agent_1` to verify basic prompt handling.

---

Commit: Refactor: Modularize project structure into core package
Author: Ishwarpatra
Date: 2025-12-16
Summary:
- Modularized `python_imply` into `core/` (analyst, architect, validator) and `engines/` (product, repair).
- Restored `LogicSpec` model and Visualizer tool functionality.
- Added automatic alphabet detection to `LogicSpec`.

---

Commit: Fix: Enforce deterministic validation and lock alphabet detection
Author: Ishwarpatra
Date: 2025-12-17
Summary:
- Hardened `DeterministicValidator` against mixed inputs and unsupported alphabets.
- Migrated core models to Pydantic V2 style (`ConfigDict`, `model_validator`).
- Removed `update_forward_refs` and replaced with future annotations.
- Visualizer tool improved: better node/edge labeling, safe filename generation.
- Added Graphviz detection and graceful fallback.

---

Commit: Add backend/java_imply files and Frontend GUI
Author: Ishwarpatra / Krishagrawal04
Date: 2025-12-24
Summary:
- Added `java_imply` implementation to backend.
- Initial implementation of the frontend GUI for Auto-DFA.
- Added example prompts and UX polish to the dashboard.
- Improved textarea shortcuts and error handling for backend failures.

---

Commit: feat: implement recursive DFA generation via product construction
Author: Ishwarpatra
Date: 2025-12-26
Summary:
- Added `ProductConstructionEngine` to combine DFAs (AND/OR).
- ArchitectAgent updated to call product engine for recursive composition.

---

Commit: fix: resolve state collision bug and improve LLM logic parsing
Author: Ishwarpatra
Date: 2025-12-28
Summary:
- Changed composite state separator from underscore `_` to pipe `|`. This fixes a critical bug where `q_dead` combined with other states caused collisions.
- Optimized ArchitectAgent and added basic security guard rails.
- Strengthened system prompts for AnalystAgent to reduce LLM hallucination (explicit JSON schema).
- Improved regex heuristics for target extraction from quoted/unquoted text.

---

Commit: Fix import path & repair engine; improve alphabet detection
Author: Ishwarpatra
Date: 2026-01-02
Summary:
- Reverted validator verbosity for cleaner logs.
- Implemented KMP-style CONTAINS logic in the repair engine.
- Hardening of `auto_repair_dfa`: reachability checks, dead-state elimination, alphabet lockdown.
- Updated `.gitignore` for editor, environment, and test artifacts.

---

Commit: feat: implement backend-frontend bridge and responsive UI
Author: Ishwarpatra / author (Iswar Patra)
Date: 2026-01-04
Summary:
- Integrated FastAPI bridge between Python backend and React frontend.
- Added Zoom and Pan functionality to the DFA diagram (React-Flow/SVG).
- Added DFA optimizer and REST API endpoints.
- Added CLI arguments to main (`model selection`, `max_product_states`).
- Initial README with project overview and setup.

---

Commit: feat: alphabet unification, N-ary combine, product-size safety checks
Author: Ishwarpatra
Date: 2026-01-14
Summary:
- Implemented alphabet unification across composite `LogicSpec` children.
- Added N-ary AND/OR combination (flattening nested trees).
- Added product-size safety estimator and thresholds.
- Default `max_product_states` set to 2000 (configurable via `AUTO_DFA_MAX_PRODUCT_STATES`).
- Added local composite splitter for fast-path "and/or" parsing.
- Revised commit record for better clarity and structure.

---

Commit: refactor(main): Remove Graphviz, add JSON export for frontend
Author: Ishwarpatra
Date: 2026-01-18
Summary:
- Removed system Graphviz dependency in favor of JSON-based diagram specs.
- Frontend now renders DFA using internal JSON representation.
- Achieved better decoupling between backend simulation and frontend visualization.

---

Commit: refactor(repair): Replace hardcoded templates with LLM-based regeneration
Author: Ishwarpatra
Date: 2026-01-20
Summary:
- Shifted repair strategy from fixed templates to LLM-guided state/transition reconstruction.
- Improved parity count regex in `LogicSpec.from_prompt`.
- Added alphabet propagation for deeply nested composite DFA specs.

---

Commit: fix(validator): correct logical error in parity counting
Author: Ishwarpatra
Date: 2026-01-23
Summary:
- Fixed a bug in the deterministic validator where parity bits were miscounted for long strings.
- Refactor(api): Improve state management and error handling for better stability.
- Finalizing validation suite for parity-related edge cases.

---

Notes
- This file is a curated activity log; additional small commits and refactors exist in the repository history that are not listed here for brevity.
- If you'd like, I can expand each entry with explicit file lists and diff summaries, or convert this into a full chronological git-style changelog with commit SHAs.
- Repository: Ishwarpatra/toc_aiagent
