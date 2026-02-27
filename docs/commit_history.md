Commit Record (History)
This document records the sequence of notable commits and feature changes for the repository.
Each entry contains: Commit: <Title>, Author: <Name>, Date (YYYY-MM-DD), and a short summary of changes.

---

Commit: refactor: implement concurrency-safe cache with context manager protocol
Author: CodeMaster (Senior Project Manager Directives)
Date: 2026-02-27
Summary:
- CRITICAL FIXES (Code Master Directives - Round 2):
  * Context Manager protocol: Added __enter__/__exit__ to DFAGeneratorSystem
  * Worker function updated to use 'with DFAGeneratorSystem() as system:' pattern
  * Guarantees deterministic cache.close() regardless of success/failure
  * Encapsulates resource management within class, not consumer

- CACHE ARCHITECTURE FIXES:
  * JSON serialization: DFA data serialized to JSON strings before diskcache storage
  * Fixes serialization failures with complex nested tuple/dict structures
  * Cache write failures now raise RuntimeError (no longer silently swallowed)
  * SQLite WAL mode enabled with 60s timeout for concurrent parallel access
  * Absolute cache directory paths to avoid multiprocessing spawn issues

- TELEMETRY FIXES:
  * Cache hit/miss counters added to ArchitectAgent (self.cache_hits/misses)
  * _worker_run_test returns cache stats in result payload
  * _emit_summary aggregates cache_hits from all worker results
  * Fixed false positive "High prompt duplication" warning
  * Warning now only fires on actual duplicate prompts (duplicate_count > 0)

- NEW FEATURES:
  * --clear-cache flag in run_qa_pipeline.py for clean cache reset via API
  * Uses cache.clear() instead of manual file deletion

- DEAD CODE REMOVAL:
  * Deleted backend/python_imply/core/cache.py (redundant SQLite DFACache)
  * Now using diskcache.Cache exclusively throughout codebase

- CONFIGURATION:
  * diskcache configured with: timeout=60, sqlite_journal_mode="wal", sqlite_synchronous=1
  * Cache directory: backend/.cache/cache.db

Test Results: All tests pass with 100% cache hit ratio on repeated runs
- cache_hits: 4, cache_misses: 0, cache_hit_ratio: 100.0
- cache_total_entries: 4, cache_volume_bytes: 32768
- No false positive warnings
- Cache persists correctly across process restarts

---

Commit: feat: Complete code review fixes for production-ready DFA pipeline
Author: CodeMaster (Senior Project Manager Directives)
Date: 2026-02-27
Summary:
- CRITICAL FIXES (Code Master Directives):
  * Fix package collision: removed stray backend/core/__init__.py causing import errors
  * Fix conftest.py: removed BACKEND_ROOT path injection, only adds PYTHON_IMPLY
  * Fix cache routing: _build_atomic_dfa now raises ValueError instead of returning None
  * Fix regex patterns: all length/numeric patterns use strict (\\d+) capture groups
  * Fix Unicode encoding: replaced box-drawing chars (└──, ✓, ✗) with ASCII (+--, OK, FAIL)
  
- NEW CORE MODULES:
  * core/cache.py: Persistent SQLite cache with model version invalidation
  * core/logging_config.py: Production logging with rotating JSON file handlers
  * core/pattern_parser.py: Centralized regex loading from patterns.json
  * core/schemas.py: Pydantic models for TestCase, TestResult, BatchSummary validation
  
- PARALLEL PROCESSING:
  * batch_verify.py: Replaced ProcessPoolExecutor with multiprocessing.Pool
  * Added _worker_run_test() stateless function for picklable parallel execution
  * Worker singleton pattern via _init_worker() initializer
  
- STRUCTURED TELEMETRY:
  * Replaced all print() statements with structlog JSON logging
  * ELK/Datadog-ready log format with key-value pairs
  * Removed ANSI color codes for CI/CD compatibility
  
- TEST FIXES (46/46 PASSED - 100%):
  * test_api.py: Fixed slowapi mocking, app.state injection, fixture setup
  * test_main.py: Fixed fixture parameter names (dfa_system, det_validator)
  * test_product.py: Updated DFA expectations to use q_dead trap state
  * test_core_logic.py: Fixed ODD_COUNT assertion (101 has 2 ones = EVEN)
  
- DEAD CODE REMOVAL:
  * Deleted backend/core/ directory (package collision source)
  * Deleted backend/scripts/multiprocess_utils.py (unused duplicate)
  
- DOCUMENTATION:
  * Added docs/CODE_REVIEW_FIXES.md with complete implementation summary

Test Results: 46/46 PASSED (100%)
- test_api.py: 14/14 PASSED
- test_core_logic.py: 15/15 PASSED
- test_main.py: 8/8 PASSED
- test_product.py: 9/9 PASSED

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

Commit: fix: stabilize QA pipeline, fix negation logic, and improve oracle truth
Author: Ishwarpatra
Date: 2026-01-31
Summary:
- Fixed critical NOT logic by implementing `complete_dfa` trap states before inversion.
- Eliminated "Phantom Tests" by discarding test cases with empty oracle data.
- Overhauled grounded truth generation: replaced hardcoded rules with high-coverage random sampling + verification (99%+ oracle coverage).
- Robustified heuristic parser in `models.py` to handle diverse phrasings (exactly, multiple of, has prefix, has substring).
- Achieved ~97.1% pass rate across a massive 6000-test suite, with 100% scores in Numeric, Length, and all forms of Negation.

---

Commit: fix(core): standardize relative imports and add type annotations
Author: Ishwarpatra
Date: 2026-02-27
Summary:
- Changed `from core.models` to `from .models` in `validator.py` and `agents.py` for consistent relative imports within `core/` package.
- Changed `from core.product` to `from .product` in `agents.py`.
- Added `Dict[str, Any]` return types to all `build_*` DFA builder functions.
- Annotated all `transitions` dict comprehensions as `Dict[str, Dict[str, str]]`.
- Fixed undefined `_cached_design_atomic` → replaced with `_build_atomic_dfa`.
- Added fallback `return None` to `_build_atomic_dfa` for unmatched logic types.
- Added `Any` to `typing` imports.

---

Commit: feat(api): add input sanitization, rate limiting, and API key auth
Author: Ishwarpatra
Date: 2026-02-27
Summary:
- Input sanitization: max 500 chars, whitespace stripping, control char rejection via Pydantic validators.
- Rate limiting via `slowapi`: 10 req/min on `/generate`, 60 req/min on `/health`.
- Optional API key authentication via `X-API-Key` header (controlled by `API_KEY` env var).
- Structured logging with request IDs and per-phase timing in `/generate` responses.
- Added `/export/json` and `/export/dot` endpoints for DFA downloads.
- Added `diskcache` and `pyyaml` to `requirements.txt`.

---

Commit: feat(main): add LLM retry with exponential backoff
Author: Ishwarpatra
Date: 2026-02-27
Summary:
- Retry `analyst.analyze` and `architect.design` up to 3x with 1s/2s/4s exponential backoff.
- Return structured error response when all LLM retries are exhausted.
- Added per-phase timing for analysis, architecture, validation, and repair stages.

---

Commit: feat(frontend): add ErrorBoundary, accessibility, and fix SVG title
Author: Ishwarpatra
Date: 2026-02-27
Summary:
- Added `ErrorBoundary` component wrapping Canvas for graceful React error handling.
- Canvas: added ARIA attributes (`role="img"`, `aria-label`, keyboard zoom `+`/`-`/`0`).
- Canvas: fixed critical bug where SVG `<title>` was overwritten by `innerHTML` in `renderDFA`. Moved `<title>` into the `svgContent` string.
- App: wrapped Canvas with ErrorBoundary.

---

Commit: test: add comprehensive API test suite and CI pipeline
Author: Ishwarpatra
Date: 2026-02-27
Summary:
- `test_api.py`: comprehensive tests for health, input validation, auth, and generation.
- `requirements-dev.txt`: pytest, pytest-cov, httpx, ruff, mypy dev dependencies.
- `.github/workflows/qa.yml`: CI workflow running unit tests with coverage reporting.
- Moved `test_functionality.py` and `test_persistent_cache.py` into `test/` directory.

---

Commit: infra: add Docker configs and environment files
Author: Ishwarpatra
Date: 2026-02-27
Summary:
- `docker-compose.yml`: full-stack orchestration (backend + frontend + ollama).
- Backend `Dockerfile` and `.dockerignore`.
- Frontend `Dockerfile` with `nginx.conf` for production serving.
- Frontend `.env` files for dev/prod/example environment configurations.

---

Commit: feat(scripts): add QA pipeline, test generation, and git hooks
Author: Ishwarpatra
Date: 2026-02-27
Summary:
- `batch_verify.py`: batch DFA verification with oracle-based ground truth.
- `generate_tests.py`: automated test case generator (6000+ test cases).
- `run_qa_pipeline.py`: full QA orchestration script.
- `retrain_analyst.py`: analyst model retraining utility.
- `show_results.py`: results display helper.
- `multiprocess_utils.py`: parallel execution utilities.
- Pre-commit hooks (bash + PowerShell) for automated smoke tests.
- `config/patterns.yaml` and `patterns.json` for pattern definitions.
- `data/` directory with CSV test datasets.

---

Commit: feat(core): add normalizer and oracle modules
Author: Ishwarpatra
Date: 2026-02-27
Summary:
- `normalizer.py`: prompt normalization for consistent parsing (YAML-based synonym mapping).
- `oracle.py`: test oracle for black-box DFA validation against ground truth.
- Archived old Java implementation to `_archive/` directory.

---

Commit: refactor: reorganize project directory structure
Author: Ishwarpatra
Date: 2026-02-27
Summary:
- Moved all documentation to `docs/`: architecture.md (renamed from dfa.md), DEPLOYMENT.md, TESTING.md, CONTRIBUTING.md, CHANGELOG.md, commit_history.md (renamed from commit.md).
- Moved root-level scripts to `scripts/`: debug_parsing.py, test_correctness.py, install-hooks.ps1.
- Renamed `dfa_result` → `scripts/sample_output.dot` (added proper .dot extension).
- Organized `backend/scripts/` into `data/`, `debug/`, `output/` subdirectories.
- Updated `.gitignore` for new paths, large data files, and cache directories.
- Updated `README.md` with full project structure tree and enriched module table.
- Created `docs/README.md` as documentation index.
- Updated `sys.path` in moved scripts to reflect new relative locations.

---

Commit: refactor(oracle): extract all Oracle logic to core/oracle.py
Author: Ishwarpatra
Date: 2026-02-27
Summary:
- Removed ~380 lines of duplicated `check_condition`, `get_oracle_strings`, `detect_contradiction`, and `CompositeOracleSolver` from `generate_tests.py`.
- `generate_tests.py` now imports all Oracle functions from `core/oracle.py` — single source of truth.
- Removed hardcoded `SAFE_AND/OR_COMBINATIONS` that overrode config values.
- All alphabet constants derived from `config/patterns.yaml`, eliminating magic strings.

---

Commit: refactor(batch_verify): parallel processing, structlog telemetry, cache metrics
Author: Ishwarpatra
Date: 2026-02-27
Summary:
- Complete rewrite of `batch_verify.py` addressing 3 architectural directives.
- **Parallel Processing**: `ProcessPoolExecutor` with stateless `_process_chunk` workers. Each worker creates its own `DFAGeneratorSystem` to avoid pickle serialization issues.
- **Structured Telemetry**: All `print()` stripped; replaced with `structlog` JSON-formatted logs. Every event emits structured key-value pairs: `{"event": "test_complete", "prompt": "...", "status": "PASS", "time_ms": 42.1}`.
- **Cache Metrics**: Tracks prompt dedup via SHA-256 hashing. Final summary emits `cache_hits`, `cache_misses`, and `cache_hit_ratio`. Regression alert at >10% duplication.

---

Commit: feat(api): add /oracle/verify endpoint and structlog dependency
Author: Ishwarpatra
Date: 2026-02-27
Summary:
- Added `/oracle/verify` POST endpoint wrapping `core/oracle.py` for production runtime monitoring.
- Accepts `op_type`, `pattern`, `alphabet`, `test_strings`; returns classified results and authoritative oracle examples.
- Added `structlog>=24.0` to `requirements.txt`.
- Bumped API version to 1.1.0.

---

Notes
- This file is a curated activity log; additional small commits and refactors exist in the repository history that are not listed here for brevity.
- If you'd like, I can expand each entry with explicit file lists and diff summaries, or convert this into a full chronological git-style changelog with commit SHAs.
- Repository: Ishwarpatra/toc_aiagent
