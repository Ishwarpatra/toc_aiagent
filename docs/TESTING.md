# Auto-DFA Testing & QA Guide

This document outlines the Quality Assurance (QA) architecture for the Auto-DFA engine. Our testing strategy combines **White Box** (internal validation) and **Black Box** (oracle verification) testing to ensure deterministic reliability.

---

## 🚀 Quick Start

**Run the full QA pipeline (1000 tests):**

```bash
python backend/scripts/run_qa_pipeline.py --count 1000
```

**Run a quick smoke test:**

```bash
python backend/scripts/batch_verify.py
```

---

## 🏗️ Architecture

The QA system consists of three main components:

### 1. Test Generator (`generate_tests.py`)

- Creates complex natural language prompts
- Uses a **Composite Oracle Solver** to mathematically generate `must_accept` and `must_reject` truth strings
- **Output:** `tests.csv`

### 2. Batch Verifier (`batch_verify.py`)

- Runs the Analyst + Architect to build a DFA
- **Internal Check:** Validates DFA against the generated `LogicSpec`
- **Oracle Check:** Simulates the DFA against the truth strings
- **Output:** `results.csv`, `failed_prompts_bank.csv`

### 3. Failure Processor (`retrain_analyst.py`)

- Harvests failures from the bank
- Generates Few-Shot Training examples for the AI
- **Output:** `few_shot_examples.jsonl`, `few_shot_examples.md`

---

## 📊 Test Result Statuses

| Status | Meaning | Action Required |
|--------|---------|-----------------|
| `PASS` | Both internal and oracle tests pass | ✅ None |
| `FAIL` | Internal validation failed | Check DFA construction |
| `ORACLE_FAIL` | Internal passed, Oracle failed | **Analyst misinterpreted prompt!** Run retraining |
| `ERROR` | Crash or exception | Debug code |

---

## 🛠️ Workflows

### 1. The Daily Dev Loop

Before pushing code, ensure you haven't broken core logic.

```bash
# 1. Install hooks (one time setup)
./install-hooks.ps1

# 2. Commit as usual
git add .
git commit -m "feat: new logic"
# (The pre-commit hook runs a 30-test smoke check automatically)
```

### 2. The "Deep Logic" Check

When working on complex features (e.g., nesting AND/OR):

```bash
cd backend/scripts

# Generate specific composite tests
python generate_tests.py --count 500 --output composite_tests.csv

# Run verification with visualization
python batch_verify.py --input composite_tests.csv --export-failed
```

Failed DFAs will be saved as `.dot` files in `failed_dfas/`.

### 3. The Retraining Loop

If the Analyst is misinterpreting prompts (e.g., failing Oracle checks):

```bash
# 1. Run a large batch and save failures
python run_qa_pipeline.py --count 2000

# 2. Collect failures
python batch_verify.py --input tests.csv --save-failures

# 3. Generate training examples
python retrain_analyst.py --markdown

# 4. Copy content from 'few_shot_examples.md' into AnalystAgent.py system prompt
```

---

## 🤖 CI/CD Integration

The pipeline runs automatically via GitHub Actions (`.github/workflows/qa.yml`).

| Trigger | Job | Scope |
|---------|-----|-------|
| Push | `unit-tests` | Fast pytest checks on core logic |
| Pull Request | `oracle-qa` | 100 generated Oracle tests + Failure Bank export |
| Main Branch | `extended-qa` | 500+ tests for regression safety |

### Artifacts

After each CI run, the following artifacts are available for download:

- `qa-results/qa_results.csv` - Full test results
- `qa-results/failed_prompts_bank.csv` - Oracle failures for retraining
- `qa-results/qa_output.log` - Console output

---

## 📁 File Reference

| File | Purpose |
|------|---------|
| `generate_tests.py` | Generate test cases with Oracle strings |
| `batch_verify.py` | Run verification with Black Box testing |
| `run_qa_pipeline.py` | Orchestrate full QA pipeline |
| `debug_repair.py` | Unit tests for DFA models |
| `retrain_analyst.py` | Process failures for retraining |
| `pre-commit` | Unix pre-commit hook |
| `pre-commit.ps1` | Windows pre-commit hook |
| `.github/workflows/qa.yml` | CI/CD workflow |

---

## ❓ Troubleshooting

### "Graphviz 'dot' binary not found"

The visualization feature requires Graphviz installed at the system level.

- **Windows:** `winget install graphviz` or download from https://graphviz.org/download/
- **Mac:** `brew install graphviz`
- **Linux:** `sudo apt-get install graphviz`

### "Oracle Failures detected"

This means the DFA is valid internally, but **logically wrong** (e.g., User asked for "Even", System built "Odd").

**Action:** Check `failed_prompts_bank.csv` and use `retrain_analyst.py`.

### "Pydantic Warnings"

Ensure you are using the V2 styles in `core/models.py`. Run `pytest` to see specific deprecation warnings.

### "LLMConnectionError"

1. Check Ollama is running: `ollama list`
2. Verify model exists: `ollama run qwen2.5-coder:1.5b`
3. Try increasing timeout in `DFAGeneratorSystem`

---

## 📈 Metrics & Goals

| Metric | Target | Critical |
|--------|--------|----------|
| Pass Rate | >95% | >80% |
| ORACLE_FAIL Rate | <5% | <10% |
| Unit Test Coverage | >80% | >60% |
| CI Pipeline Duration | <10min | <20min |

---

## 🧪 Edge Case Test Examples

The following edge cases are covered by test suites and should be validated when making changes:

### Input Validation Edge Cases

| Input | Expected Behavior | Test File |
|-------|-------------------|-----------|
| Empty string `""` | Rejected (422) | `test/test_api.py` |
| Whitespace-only `"   "` | Rejected after stripping (422) | `test/test_api.py` |
| 501+ characters | Rejected – exceeds limit (422) | `test/test_api.py` |
| Control characters `"\x00\x01"` | Stripped, then processed normally | `test/test_api.py` |
| Missing `prompt` field | Rejected (422) | `test/test_api.py` |

### DFA Logic Edge Cases

| Prompt | Logic Type | Key Behavior | Test File |
|--------|-----------|-------------|-----------|
| `"starts with ''"` (empty target) | STARTS_WITH | Should match all strings | `test/test_core_logic.py` |
| `"divisible by 3"` with `alphabet=['0','1']` | DIVISIBLE_BY | Binary interpretation | `test/test_core_logic.py` |
| `"even number of 1s"` on empty string | EVEN_COUNT | Should accept (0 is even) | `test/test_core_logic.py` |
| `"contains '110'"` | CONTAINS | KMP substring matching | `test/test_core_logic.py` |
| `"not contains '00'"` | NOT_CONTAINS | Complement of CONTAINS | `test/test_core_logic.py` |
| `"product is even"` on `"1111"` | PRODUCT_EVEN | Should reject (all 1s) | `test/test_core_logic.py` |

### Advanced / Composite Logic

| Prompt | Expected Behavior |
|--------|-------------------|
| `"starts with 'a' and ends with 'b'"` | Product construction (AND) |
| `"contains '11' or ends with '01'"` | Product construction (OR) |
| `"starts with '101' and divisible by 3 and contains '11'"` | 3-way product composition |
| `"strings with even number of a's and odd number of b's"` | Multi-constraint composition |

### Security Edge Cases

| Scenario | Expected | Test File |
|----------|----------|-----------|
| No API key (auth disabled) | 200 | `test/test_api.py` |
| Missing key (auth enabled) | 401 | `test/test_api.py` |
| Wrong key (auth enabled) | 401 | `test/test_api.py` |
| Rate limit exceeded (>10/min) | 429 | Manual verification |

---

## 🔬 Running Coverage Reports Locally

```bash
# Install dev dependencies
cd backend/python_imply
pip install -r requirements-dev.txt

# Run with coverage
python -m pytest test/ -v --cov=core --cov=. --cov-report=term-missing

# Generate HTML report
python -m pytest test/ --cov=core --cov-report=html
# Open htmlcov/index.html in browser
```

Coverage targets: **>80%** for core logic, **>60%** critical threshold.

---

## 🔄 Continuous Improvement

The system is designed for continuous improvement through the feedback loop:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Run Tests   │────▶│ Collect      │────▶│  Generate    │
│              │     │ ORACLE_FAILs │     │  Training    │
└──────────────┘     └──────────────┘     │  Examples    │
       ▲                                   └──────┬───────┘
       │                                          │
       │         ┌──────────────┐                 │
       └─────────│  Update      │◀────────────────┘
                 │  AnalystAgent│
                 └──────────────┘
```

---

*Last Updated: 2026-01-31*  
*Auto-DFA QA System v2.0*
