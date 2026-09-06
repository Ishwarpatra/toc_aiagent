# Auto-DFA Testing & QA Guide

This document outlines the Quality Assurance (QA) and test architecture for the Auto-DFA engine.

---

## Test Suites & Coverage

The automated test suite in `backend/src/tests/` verifies the entire system:

| Test File | Focus Area | Key Checks |
| :--- | :--- | :--- |
| `test_grammar.py` | Right-Linear Grammar Engine | State mapping, transition rules ($S \to aA$), accept state epsilon productions ($A \to \varepsilon$), grammar formatting |
| `test_reverse_engineer.py` | Image-to-Language Pipeline | VisionAgent parsing, structural validation, DescriberAgent synthesis, Gemini/OpenRouter providers, `/reverse-engineer` endpoint |
| `test_product_engine.py` | Product Construction | Union, intersection, inversion, minimization across complex composite specifications |
| `test_optimizer.py` | DFA Optimizer | Hopcroft/BFS state pruning, unreachable and non-productive state removal |
| `test_repair.py` | Repair Engine | Fault localization, LLM auto-repair retries, structural cleanup |
| `test_api.py` | REST API | `/generate`, `/health`, `/export/json`, `/export/dot`, rate limiting, API key auth |
| `test_core_logic.py` | Atomic Logic Builders | Prefixes, suffixes, substrings, modulo counts, parity, exact/min/max lengths |
| `test_oracle.py` | Truth Oracle | Ground-truth string generation and verification |

---

## Running Tests

### 1. Run Full Pytest Suite

```bash
cd backend/src
python -m pytest tests/ -v
```

**Result:** `421 passed in ~7.0s`

### 2. Run with Coverage Report

```bash
cd backend/src
python -m pytest tests/ --cov=core --cov-report=term-missing
```

### 3. Run Specific Test Modules

```bash
python -m pytest tests/test_grammar.py -v
python -m pytest tests/test_reverse_engineer.py -v
```

---

## QA Batch Verification Framework

The QA system in `backend/qa/` provides stress-testing and truth-table verification:

- `generate_tests.py`: Generates randomized and edge-case natural language prompts with ground-truth test strings.
- `batch_verify.py`: Runs the full pipeline against batch prompts and verifies accuracy against ground truth.
- `run_qa_pipeline.py`: End-to-end automated benchmark suite.
