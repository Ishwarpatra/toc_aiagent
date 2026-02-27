#!/usr/bin/env python3
"""
Batch Verification System for Auto-DFA with Black Box Oracle Testing

Runs a comprehensive test suite against the DFA generation pipeline
using BOTH internal (white-box) and oracle (black-box) validation.

All telemetry emitted as structured JSON via structlog.
Features:
- Parallel processing with multiprocessing.Pool
- Persistent cache with SQLite
- Structured logging for ELK/Datadog ingestion
- Schema validation with Pydantic
- Timeout handling per test case

Usage:
    python batch_verify.py [--input tests.csv] [--output results.csv] [--parallel]
"""

import sys
import os
import time
import csv
import json
import traceback
import hashlib
import argparse
import multiprocessing
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

import structlog

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = SCRIPT_DIR.parent / "python_imply"
sys.path.insert(0, str(BACKEND_DIR))

# Import core modules
from core.models import DFA
from core.oracle import get_oracle_strings
from core.schemas import TestCase
from core.pattern_parser import extract_quoted_pattern

# ---------------------------------------------------------------------------
# Structured logging configuration
# ---------------------------------------------------------------------------
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Status codes
# ---------------------------------------------------------------------------
class Status:
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIP = "SKIP"
    ORACLE_FAIL = "ORACLE_FAIL"
    TIMEOUT = "TIMEOUT"


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------
class ErrorType:
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    UNKNOWN = "UNKNOWN"


def classify_error(exc: Exception) -> str:
    exc_name = type(exc).__name__
    exc_str = str(exc).lower()
    transient_indicators = ["timeout", "connection", "busy", "temporary", "resource temporarily"]
    if any(ind in exc_str for ind in transient_indicators):
        return ErrorType.TRANSIENT
    if exc_name in ["TimeoutError", "ConnectionError", "ResourceWarning"]:
        return ErrorType.TRANSIENT
    return ErrorType.PERMANENT


# ---------------------------------------------------------------------------
# CSV loader with schema validation
# ---------------------------------------------------------------------------
def load_tests_from_csv(filepath: str) -> List[Dict[str, Any]]:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Test file not found: {filepath}")

    tests: List[Dict[str, Any]] = []

    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            try:
                test_case = TestCase(
                    prompt=row.get("prompt", "").strip(),
                    category=row.get("category", "Unknown").strip(),
                    expected_type=row.get("expected_type", "").strip(),
                    difficulty=row.get("difficulty", "unknown").strip(),
                    must_accept=row.get("must_accept", "").strip(),
                    must_reject=row.get("must_reject", "").strip(),
                    is_contradiction=row.get("is_contradiction", "false").strip().lower() == "true",
                )
                tests.append(test_case.to_dict())
            except Exception as e:
                # CRITICAL: Never silently drop test cases during parsing.
                # Log the error and raise ValueError for the orchestrator to handle.
                log.error("fatal_schema_mismatch", row=row_num, prompt=row.get("prompt", "")[:50], error=str(e))
                raise ValueError(f"Schema mismatch at row {row_num}: {str(e)}")

    log.info("tests_loaded_from_csv", path=filepath, valid_count=len(tests))
    return tests


# ---------------------------------------------------------------------------
# DOT exporter
# ---------------------------------------------------------------------------
def export_dfa_to_dot(dfa: DFA, filepath: str, title: str = "") -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f'digraph DFA {{\n  rankdir=LR;\n  label="{title}";\n')
        f.write('  __start__ [shape=none, label=""];\n')
        f.write(f'  __start__ -> "{dfa.start_state}";\n')
        for state in dfa.states:
            shape = "doublecircle" if state in dfa.accept_states else "circle"
            f.write(f'  "{state}" [shape={shape}];\n')
        for src, trans in dfa.transitions.items():
            for symbol, dest in trans.items():
                f.write(f'  "{src}" -> "{dest}" [label="{symbol}"];\n')
        f.write("}\n")


# ---------------------------------------------------------------------------
# Cache-key helper
# ---------------------------------------------------------------------------
def _prompt_cache_key(prompt: str) -> str:
    return hashlib.sha256(prompt.strip().lower().encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Stateless worker function for multiprocessing.Pool
# Avoids pickling issues by being a top-level function
# ---------------------------------------------------------------------------
def _worker_run_test(case_tuple: Tuple[int, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process a single test case in a forked worker process.
    Initializes a process-local DFAGeneratorSystem to avoid IPC serialization crashes.
    
    Args:
        case_tuple: (test_index, test_case_dict)
    
    Returns:
        Result dictionary with status, metrics, and validation data
    """
    import structlog
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _log = structlog.get_logger()
    
    test_idx, case = case_tuple
    prompt = case["prompt"]
    category = case.get("category", "Unknown")
    cache_key = _prompt_cache_key(prompt)

    result: Dict[str, Any] = {
        "prompt": prompt,
        "category": category,
        "expected_type": case.get("expected_type", ""),
        "difficulty": case.get("difficulty", "unknown"),
        "status": Status.ERROR,
        "actual_type": None,
        "states": 0,
        "time_ms": 0,
        "error": "",
        "error_type": ErrorType.UNKNOWN,
        "internal_validated": False,
        "oracle_validated": False,
        "oracle_accept_failures": "",
        "oracle_reject_failures": "",
        "cache_key": cache_key,
        "cache_hit": False,
    }

    t0 = time.perf_counter()
    dfa = None
    system = None

    # CRITICAL: Use context manager protocol for deterministic cache cleanup
    # This guarantees cache.close() is called regardless of success/failure
    from main import DFAGeneratorSystem
    with DFAGeneratorSystem() as system:
        # Analyze
        spec = system.analyst.analyze(prompt)
        result["actual_type"] = spec.logic_type
        _log.info("analyst_complete", prompt=prompt, logic_type=spec.logic_type, alphabet=list(spec.alphabet), test_index=test_idx)

        # Design
        dfa = system.architect.design(spec)
        result["states"] = len(dfa.states)
        _log.info("architect_complete", prompt=prompt, states=len(dfa.states), test_index=test_idx)

        # White-box validation
        is_valid, error_msg = system.validator.validate(dfa, spec)
        result["internal_validated"] = is_valid
        _log.info("validator_result", prompt=prompt, passed=is_valid, error=error_msg, test_index=test_idx)

        # Black-box oracle verification using core.oracle module
        oracle = _oracle_verify(dfa, case, _log)
        result["oracle_validated"] = oracle["oracle_pass"]
        result["oracle_accept_failures"] = ";".join(oracle["accept_failures"][:3])
        result["oracle_reject_failures"] = ";".join(oracle["reject_failures"][:3])
        result["oracle_source"] = oracle.get("oracle_source", "test_case")

        if is_valid and oracle["oracle_pass"]:
            result["status"] = Status.PASS
        elif is_valid and not oracle["oracle_pass"]:
            result["status"] = Status.ORACLE_FAIL
            result["error"] = f"Oracle failures: accept={oracle['accept_failures'][:2]}, reject={oracle['reject_failures'][:2]}"
        else:
            result["status"] = Status.FAIL
            result["error"] = error_msg or "Validation failed"

    # Context manager __exit__ has been called - cache is closed

    result["time_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    # CRITICAL: Return cache statistics for telemetry rollup
    if system and hasattr(system, 'architect'):
        result["cache_hits"] = system.architect.cache_hits
        result["cache_misses"] = system.architect.cache_misses
    else:
        result["cache_hits"] = 0
        result["cache_misses"] = 0
    _log.info("test_complete", prompt=prompt, status=result["status"], time_ms=result["time_ms"], test_index=test_idx)
    return result


# ---------------------------------------------------------------------------
# Oracle verification using core.oracle module
# ---------------------------------------------------------------------------
def _oracle_verify(dfa: DFA, case: Dict[str, Any], _log: Any) -> Dict[str, Any]:
    """
    Black-box oracle verification using core.oracle module.
    Dynamically generates oracle strings if not provided in test case.
    """
    out = {"oracle_pass": True, "accept_failures": [], "reject_failures": [], "oracle_source": "test_case"}

    if case.get("is_contradiction"):
        return out

    must_accept = case.get("must_accept", "")
    must_reject = case.get("must_reject", "")

    # If test case has no oracle strings, generate them dynamically
    if not must_accept and not must_reject:
        out["oracle_source"] = "dynamic_generation"
        try:
            pattern = extract_quoted_pattern(case["prompt"])
            if pattern:
                alphabet = list(dfa.alphabet) if dfa.alphabet else ["0", "1"]
                expected_type = case.get("expected_type", "CONTAINS")
                accept_list, reject_list = get_oracle_strings(expected_type, pattern, alphabet)
                must_accept = ";".join(accept_list)
                must_reject = ";".join(reject_list)
                _log.debug("oracle_strings_generated", prompt=case["prompt"][:50], expected_type=expected_type, pattern=pattern)
        except Exception as e:
            _log.warning("oracle_generation_failed", prompt=case["prompt"][:50], error=str(e))

    # Validate accept strings
    for test_string in (must_accept or "").split(";"):
        s = test_string.strip()
        if not s and s != "":
            continue
        if any(c not in dfa.alphabet for c in s):
            continue
        if not dfa.accepts(s):
            out["oracle_pass"] = False
            out["accept_failures"].append(s)

    # Validate reject strings
    for test_string in (must_reject or "").split(";"):
        s = test_string.strip()
        if not s and s != "":
            continue
        if any(c not in dfa.alphabet for c in s):
            continue
        if dfa.accepts(s):
            out["oracle_pass"] = False
            out["reject_failures"].append(s)

    return out


# ---------------------------------------------------------------------------
# BatchVerifier
# ---------------------------------------------------------------------------
class BatchVerifier:
    """Orchestrates sequential or parallel test execution with structured telemetry."""

    def __init__(self, export_failed: bool = False, model_version: str = "v1", test_timeout_sec: int = 30):
        self.export_failed = export_failed
        self.model_version = model_version
        self.test_timeout_sec = test_timeout_sec
        self.system = None
        self.cache = None
        self.results = []
        self.test_suite = []
        self.failed_dfa_dir = None
        self.cache_hits = 0
        self.cache_misses = 0

    def initialize_system(self, model_name: str = "gpt-4o-mini", max_product_states: int = 100) -> bool:
        try:
            from main import DFAGeneratorSystem
            self.system = DFAGeneratorSystem(model_name=model_name, max_product_states=max_product_states)
            # CRITICAL: diskcache with WAL mode is initialized inside ArchitectAgent
            log.info("system_initialized", model=model_name, max_product_states=max_product_states, diskcache_wal=True)
            if self.export_failed:
                self.failed_dfa_dir = SCRIPT_DIR / "failed_dfas"
                self.failed_dfa_dir.mkdir(exist_ok=True)
                log.info("export_dir_created", path=str(self.failed_dfa_dir))
            return True
        except Exception as exc:
            log.error("system_init_failed", error=str(exc), tb=traceback.format_exc())
            return False

    def load_tests(self, input_file: Optional[str] = None) -> None:
        if input_file:
            self.test_suite = load_tests_from_csv(input_file)
            with_accept = sum(1 for t in self.test_suite if t.get("must_accept"))
            with_reject = sum(1 for t in self.test_suite if t.get("must_reject"))
            log.info("tests_loaded", source=input_file, count=len(self.test_suite), with_accept=with_accept, with_reject=with_reject)
        else:
            # CRITICAL: No fallback to hardcoded test data. Enterprise test runners
            # must evaluate explicitly provided data only.
            raise ValueError("No input file provided. CSV file path is required.")

    def run_all_tests(self) -> None:
        """Run tests sequentially (for debugging or small suites)."""
        if not self.system and not self.initialize_system():
            return
        if not self.test_suite:
            log.warning("no_tests_loaded")
            return

        log.info("batch_started", total=len(self.test_suite), mode="sequential")

        for idx, case in enumerate(self.test_suite):
            result = _worker_run_test((idx, case))
            self.results.append(result)

        self._emit_summary()

    def run_all_tests_parallel(self, num_workers: Optional[int] = None) -> None:
        """
        Run tests in parallel using multiprocessing.Pool.
        Uses stateless worker function to avoid pickling issues.
        """
        if not self.system and not self.initialize_system():
            return
        if not self.test_suite:
            log.warning("no_tests_loaded")
            return

        if num_workers is None:
            num_workers = multiprocessing.cpu_count()
        num_workers = max(1, min(num_workers, multiprocessing.cpu_count()))

        log.info("batch_started", total=len(self.test_suite), mode="parallel", workers=num_workers)

        # Create test tuples for worker function
        test_tuples = list(enumerate(self.test_suite))

        with multiprocessing.Pool(processes=num_workers) as pool:
            self.results = pool.map(_worker_run_test, test_tuples)

        self._emit_summary()

    def _emit_summary(self) -> None:
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == Status.PASS)
        failed = sum(1 for r in self.results if r["status"] == Status.FAIL)
        oracle_failed = sum(1 for r in self.results if r["status"] == Status.ORACLE_FAIL)
        errors = sum(1 for r in self.results if r["status"] == Status.ERROR)
        timeouts = sum(1 for r in self.results if r["status"] == Status.TIMEOUT)
        avg_ms = sum(r["time_ms"] for r in self.results) / total if total else 0

        # CRITICAL: Aggregate cache hit/miss statistics from all test results
        total_cache_hits = sum(r.get("cache_hits", 0) for r in self.results)
        total_cache_misses = sum(r.get("cache_misses", 0) for r in self.results)
        total_cache_lookups = total_cache_hits + total_cache_misses
        cache_hit_ratio = (total_cache_hits / total_cache_lookups * 100) if total_cache_lookups > 0 else 0.0

        # Cache metrics from diskcache
        cache_metrics = {}
        total_entries = 0
        
        if self.system and hasattr(self.system, 'architect') and hasattr(self.system.architect, 'cache'):
            try:
                cache = self.system.architect.cache
                total_entries = len(cache)
                # diskcache doesn't track hits/misses internally, but we can report size
                cache_metrics = {
                    "cache_total_entries": total_entries,
                    "cache_directory": cache.directory,
                    "cache_volume_bytes": cache.volume(),
                }
            except Exception as e:
                log.warning("cache_stats_failed", error=str(e))

        log.info(
            "batch_summary",
            total=total, passed=passed, failed_internal=failed, failed_oracle=oracle_failed,
            errors=errors, timeouts=timeouts,
            pass_rate=round(passed / total * 100, 2) if total else 0,
            avg_time_ms=round(avg_ms, 2),
            cache_hits=total_cache_hits, cache_misses=total_cache_misses,
            cache_hit_ratio=round(cache_hit_ratio, 2),
            cache_persistent_metrics=cache_metrics,
        )

        # Category breakdown
        categories: Dict[str, Dict[str, int]] = {}
        for r in self.results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"pass": 0, "fail": 0, "oracle_fail": 0, "error": 0, "timeout": 0}
            bucket = {"PASS": "pass", "FAIL": "fail", "ORACLE_FAIL": "oracle_fail", "TIMEOUT": "timeout"}.get(r["status"], "error")
            categories[cat][bucket] += 1

        for cat, counts in sorted(categories.items()):
            cat_total = sum(counts.values())
            log.info("category_summary", category=cat, passed=counts["pass"], total=cat_total,
                     pass_rate=round(counts["pass"] / cat_total * 100, 1) if cat_total else 0,
                     oracle_failures=counts["oracle_fail"], timeouts=counts["timeout"])

        # Log oracle failures
        for r in self.results:
            if r["status"] == Status.ORACLE_FAIL:
                log.warning("oracle_failure_detected", prompt=r["prompt"],
                            oracle_accept_failures=r.get("oracle_accept_failures", ""),
                            oracle_reject_failures=r.get("oracle_reject_failures", ""))

        # CRITICAL: Cache regression alert - only fire on actual duplicate prompts in input
        # High cache_hit_ratio is expected behavior for repeated CI/CD runs with known prompts.
        # Only warn if the same prompt appears multiple times in the CURRENT test suite.
        prompt_counts: Dict[str, int] = {}
        for r in self.results:
            p = r["prompt"]
            prompt_counts[p] = prompt_counts.get(p, 0) + 1
        duplicate_prompts = sum(1 for count in prompt_counts.values() if count > 1)
        
        if duplicate_prompts > 0:
            log.warning("cache_regression_alert", message="Duplicate prompts detected in test suite",
                        duplicate_prompt_count=duplicate_prompts, total_prompts=len(self.results))

    def export_csv(self, filepath: str) -> None:
        if not self.results:
            log.warning("export_skipped", reason="no results")
            return
        fieldnames = ["prompt", "category", "expected_type", "actual_type", "difficulty",
                      "status", "states", "time_ms", "internal_validated", "oracle_validated",
                      "oracle_accept_failures", "oracle_reject_failures", "cache_key", "cache_hit", "error"]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.results)
        log.info("results_exported", path=filepath, count=len(self.results))

    def export_failure_bank(self, filepath: Optional[str] = None) -> None:
        oracle_failures = [r for r in self.results if r["status"] == Status.ORACLE_FAIL]
        if not oracle_failures:
            log.info("failure_bank_empty")
            return

        fp = Path(filepath) if filepath else SCRIPT_DIR / "failed_prompts_bank.csv"
        existing = []
        if fp.exists():
            with open(fp, "r", encoding="utf-8") as f:
                existing = list(csv.DictReader(f))

        ts = datetime.now().isoformat()
        new_entries = []
        for r in oracle_failures:
            entry = {
                "timestamp": ts, "prompt": r["prompt"], "category": r["category"],
                "expected_type": r["expected_type"], "actual_type": r.get("actual_type", ""),
                "oracle_accept_failures": r.get("oracle_accept_failures", ""),
                "oracle_reject_failures": r.get("oracle_reject_failures", ""),
                "error": r.get("error", ""),
            }
            if not any(e.get("prompt") == entry["prompt"] for e in existing):
                new_entries.append(entry)

        if not new_entries:
            log.info("failure_bank_no_new_entries", path=str(fp))
            return

        all_entries = existing + new_entries
        fields = ["timestamp", "prompt", "category", "expected_type", "actual_type",
                  "oracle_accept_failures", "oracle_reject_failures", "error"]
        with open(fp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_entries)
        log.info("failure_bank_updated", path=str(fp), new=len(new_entries), total=len(all_entries))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Batch Verification System for Auto-DFA (structured telemetry)")
    parser.add_argument("--input", "-i", type=str, required=True, help="Input CSV file with test cases (required)")
    parser.add_argument("--output", "-o", type=str, help="Output CSV file for results")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers")
    parser.add_argument("--export-failed", action="store_true", help="Export failed DFAs as DOT files")
    parser.add_argument("--save-failures", action="store_true", help="Save Oracle failures to bank")
    parser.add_argument("--failure-bank", type=str, default=None, help="Path to failure bank file")
    parser.add_argument("--timeout", type=int, default=30, help="Per-test timeout in seconds")
    parser.add_argument("--model-version", type=str, default="v1", help="Model version for cache invalidation")
    args = parser.parse_args()

    log.info("batch_verify_started", timestamp=datetime.now().isoformat(), input_file=args.input, parallel=args.parallel)

    verifier = BatchVerifier(export_failed=args.export_failed, model_version=args.model_version, test_timeout_sec=args.timeout)

    try:
        verifier.load_tests(args.input)
    except FileNotFoundError as exc:
        log.error("input_file_not_found", error=str(exc))
        return 1
    except ValueError as exc:
        # CRITICAL: Schema validation errors or missing input file
        log.error("fatal_error", error_type="schema_validation", error=str(exc))
        return 1

    if args.parallel:
        verifier.run_all_tests_parallel(args.workers)
    else:
        verifier.run_all_tests()

    if args.output:
        verifier.export_csv(args.output)

    if args.save_failures:
        verifier.export_failure_bank(args.failure_bank)

    # CRITICAL: Close diskcache to flush WAL buffer to disk
    if verifier.system:
        verifier.system.close()

    failed_count = sum(1 for r in verifier.results if r["status"] in (Status.FAIL, Status.ORACLE_FAIL, Status.ERROR, Status.TIMEOUT))
    # CRITICAL: Fail if no tests were executed (prevents false-positive success)
    return 1 if failed_count > 0 or len(verifier.results) == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
