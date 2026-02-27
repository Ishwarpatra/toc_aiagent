#!/usr/bin/env python3
"""
Batch Verification System for Auto-DFA with Black Box Oracle Testing

Runs a comprehensive test suite against the DFA generation pipeline
using BOTH internal (white-box) and oracle (black-box) validation.

All telemetry emitted as structured JSON via structlog.

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
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

import structlog

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = SCRIPT_DIR.parent / "python_imply"
sys.path.insert(0, str(BACKEND_DIR))

from main import DFAGeneratorSystem
from core.models import DFA

# ---------------------------------------------------------------------------
# Structured logging configuration — JSON output for Datadog/ELK ingestion
# ---------------------------------------------------------------------------
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
    logger_factory=structlog.PrintLoggerFactory(),
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


# ---------------------------------------------------------------------------
# DEFAULT TEST SUITE (built-in, used when no CSV provided)
# ---------------------------------------------------------------------------
DEFAULT_TEST_SUITE: List[Dict[str, Any]] = [
    {"prompt": "starts with 'a'",     "category": "Atomic", "expected_type": "STARTS_WITH",
     "must_accept": "a;ab;aa;abc",    "must_reject": "b;ba;bab"},
    {"prompt": "starts with 'ab'",    "category": "Atomic", "expected_type": "STARTS_WITH",
     "must_accept": "ab;aba;abb;abab","must_reject": "a;ba;aab;b"},
    {"prompt": "ends with 'b'",       "category": "Atomic", "expected_type": "ENDS_WITH",
     "must_accept": "b;ab;aab;bb",    "must_reject": "a;ba;aba"},
    {"prompt": "ends with '01'",      "category": "Atomic", "expected_type": "ENDS_WITH",
     "must_accept": "01;001;101;0101","must_reject": "0;1;10;00;11"},
    {"prompt": "contains '01'",       "category": "Atomic", "expected_type": "CONTAINS",
     "must_accept": "01;001;010;101;0100", "must_reject": "0;1;00;11;10"},
    {"prompt": "contains 'aa'",       "category": "Atomic", "expected_type": "CONTAINS",
     "must_accept": "aa;aaa;baa;aab", "must_reject": "a;b;ab;ba;aba"},
    {"prompt": "not contains '11'",   "category": "Atomic", "expected_type": "NOT_CONTAINS",
     "must_accept": "0;1;01;10;010;101", "must_reject": "11;011;110;111;0110"},
    {"prompt": "length is 3",         "category": "Atomic_Length", "expected_type": "EXACT_LENGTH",
     "must_accept": "000;001;010;011;100;101;110;111", "must_reject": ";0;00;0000;00000"},
    {"prompt": "length is 5",         "category": "Atomic_Length", "expected_type": "EXACT_LENGTH",
     "must_accept": "00000;00001;11111", "must_reject": ";0;0000;000000"},
    {"prompt": "divisible by 2",      "category": "Atomic_Numeric", "expected_type": "DIVISIBLE_BY",
     "must_accept": "0;10;100;110",   "must_reject": "1;11;101;111"},
    {"prompt": "divisible by 3",      "category": "Atomic_Numeric", "expected_type": "DIVISIBLE_BY",
     "must_accept": "0;11;110;1001",  "must_reject": "1;10;100;101"},
    {"prompt": "even number of 1s",   "category": "Atomic_Count", "expected_type": "EVEN_COUNT",
     "must_accept": ";0;00;11;101;0110", "must_reject": "1;01;10;111;1101"},
    {"prompt": "odd number of 0",     "category": "Atomic_Count", "expected_type": "ODD_COUNT",
     "must_accept": "0;100;010;001;111110", "must_reject": ";1;00;1001;0110"},
    {"prompt": "no consecutive 1s",   "category": "Atomic_Constraint", "expected_type": "NO_CONSECUTIVE",
     "must_accept": ";0;1;01;10;010;101;0101", "must_reject": "11;011;110;111;101011"},
    {"prompt": "starts with 'a' and ends with 'b'", "category": "Composite_Same", "expected_type": "AND",
     "must_accept": "ab;aab;abb;abab;aabb", "must_reject": "a;b;ba;aa;bb;aba"},
    {"prompt": "contains '00' or contains '11'", "category": "Composite_Same", "expected_type": "OR",
     "must_accept": "00;11;001;011;100;110;0011", "must_reject": ";0;1;01;10;010;101"},
    {"prompt": "does not start with 'a'", "category": "Negation", "expected_type": "NOT_STARTS_WITH",
     "must_accept": "b;ba;bb;bab",    "must_reject": "a;ab;aa;aba"},
]


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------
def load_tests_from_csv(filepath: str) -> List[Dict[str, Any]]:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Test file not found: {filepath}")
    tests: List[Dict[str, Any]] = []
    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            test: Dict[str, Any] = {
                "prompt": row.get("prompt", "").strip(),
                "category": row.get("category", "Unknown").strip(),
                "expected_type": row.get("expected_type", "").strip(),
                "difficulty": row.get("difficulty", "unknown").strip(),
                "must_accept": row.get("must_accept", "").strip(),
                "must_reject": row.get("must_reject", "").strip(),
                "is_contradiction": row.get("is_contradiction", "false").strip().lower() == "true",
            }
            if test["prompt"]:
                tests.append(test)
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
# Cache-key helper (for dedup tracking)
# ---------------------------------------------------------------------------
def _prompt_cache_key(prompt: str) -> str:
    """Deterministic cache key for a prompt."""
    return hashlib.sha256(prompt.strip().lower().encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Stateless worker function (picklable for ProcessPoolExecutor)
# ---------------------------------------------------------------------------
def _run_single_test_stateless(
    case: Dict[str, Any],
    test_index: int,
    model_name: str,
    max_product_states: int,
) -> Dict[str, Any]:
    """
    Process a single test case in a forked worker process.
    Must be stateless — creates its own DFAGeneratorSystem.
    """
    _log = structlog.get_logger()
    prompt = case["prompt"]
    category = case.get("category", "Unknown")

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
        "internal_validated": False,
        "oracle_validated": False,
        "oracle_accept_failures": "",
        "oracle_reject_failures": "",
        "cache_key": _prompt_cache_key(prompt),
    }

    t0 = time.perf_counter()
    dfa = None

    try:
        system = DFAGeneratorSystem(model_name=model_name, max_product_states=max_product_states)

        # Analyze
        spec = system.analyst.analyze(prompt)
        result["actual_type"] = spec.logic_type
        _log.info("analyst_complete", prompt=prompt, logic_type=spec.logic_type,
                   alphabet=list(spec.alphabet), test_index=test_index)

        # Design
        dfa = system.architect.design(spec)
        result["states"] = len(dfa.states)
        _log.info("architect_complete", prompt=prompt, states=len(dfa.states),
                   test_index=test_index)

        # White-box validation
        is_valid, error_msg = system.validator.validate(dfa, spec)
        result["internal_validated"] = is_valid
        _log.info("validator_result", prompt=prompt, passed=is_valid,
                   error=error_msg, test_index=test_index)

        # Black-box oracle verification
        oracle = _oracle_verify(dfa, case)
        result["oracle_validated"] = oracle["oracle_pass"]
        result["oracle_accept_failures"] = ";".join(oracle["accept_failures"][:3])
        result["oracle_reject_failures"] = ";".join(oracle["reject_failures"][:3])

        if is_valid and oracle["oracle_pass"]:
            result["status"] = Status.PASS
        elif is_valid and not oracle["oracle_pass"]:
            result["status"] = Status.ORACLE_FAIL
            result["error"] = (
                f"Oracle failures: accept={oracle['accept_failures'][:2]}, "
                f"reject={oracle['reject_failures'][:2]}"
            )
        else:
            result["status"] = Status.FAIL
            result["error"] = error_msg or "Validation failed"

    except Exception as exc:
        result["status"] = Status.ERROR
        result["error"] = str(exc)
        _log.error("test_error", prompt=prompt, error=str(exc),
                    tb=traceback.format_exc(), test_index=test_index)

    result["time_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    _log.info("test_complete", prompt=prompt, status=result["status"],
               time_ms=result["time_ms"], test_index=test_index)
    return result


def _oracle_verify(dfa: DFA, case: Dict[str, Any]) -> Dict[str, Any]:
    """Black-box oracle verification against must_accept / must_reject strings."""
    out: Dict[str, Any] = {"oracle_pass": True, "accept_failures": [], "reject_failures": []}

    if case.get("is_contradiction"):
        return out

    for test_string in (case.get("must_accept", "") or "").split(";"):
        s = test_string.strip()
        if not s and s != "":
            continue
        if any(c not in dfa.alphabet for c in s):
            continue
        if not dfa.accepts(s):
            out["oracle_pass"] = False
            out["accept_failures"].append(s)

    for test_string in (case.get("must_reject", "") or "").split(";"):
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
# Process a chunk of tests (for ProcessPoolExecutor)
# ---------------------------------------------------------------------------
def _process_chunk(args: tuple) -> List[Dict[str, Any]]:
    """Stateless chunk processor — each worker gets its own system."""
    chunk, chunk_idx, model_name, max_product_states = args
    results: List[Dict[str, Any]] = []
    for local_idx, case in enumerate(chunk):
        global_idx = chunk_idx * len(chunk) + local_idx
        r = _run_single_test_stateless(case, global_idx, model_name, max_product_states)
        results.append(r)
    return results


# ---------------------------------------------------------------------------
# BatchVerifier
# ---------------------------------------------------------------------------
class BatchVerifier:
    """Orchestrates sequential or parallel test execution with structured telemetry."""

    def __init__(self, export_failed: bool = False):
        self.export_failed = export_failed
        self.system: Optional[DFAGeneratorSystem] = None
        self.results: List[Dict[str, Any]] = []
        self.test_suite: List[Dict[str, Any]] = []
        self.failed_dfa_dir: Optional[Path] = None
        # Cache dedup tracking
        self._seen_keys: Dict[str, int] = {}
        self.cache_hits = 0
        self.cache_misses = 0

    # -- initialise -----------------------------------------------------
    def initialize_system(self) -> bool:
        try:
            self.system = DFAGeneratorSystem()
            log.info("system_initialized", model=self.system.model_name)
            if self.export_failed:
                self.failed_dfa_dir = SCRIPT_DIR / "failed_dfas"
                self.failed_dfa_dir.mkdir(exist_ok=True)
                log.info("export_dir_created", path=str(self.failed_dfa_dir))
            return True
        except Exception as exc:
            log.error("system_init_failed", error=str(exc))
            return False

    # -- load tests -----------------------------------------------------
    def load_tests(self, input_file: Optional[str] = None) -> None:
        if input_file:
            self.test_suite = load_tests_from_csv(input_file)
            with_accept = sum(1 for t in self.test_suite if t.get("must_accept"))
            with_reject = sum(1 for t in self.test_suite if t.get("must_reject"))
            log.info("tests_loaded", source=input_file, count=len(self.test_suite),
                     with_accept=with_accept, with_reject=with_reject)
        else:
            self.test_suite = DEFAULT_TEST_SUITE
            log.info("tests_loaded", source="built-in", count=len(self.test_suite))

    # -- sequential run -------------------------------------------------
    def run_all_tests(self) -> None:
        if not self.system and not self.initialize_system():
            return
        if not self.test_suite:
            log.warning("no_tests_loaded")
            return

        log.info("batch_started", total=len(self.test_suite), mode="sequential")

        for idx, case in enumerate(self.test_suite):
            key = _prompt_cache_key(case["prompt"])
            if key in self._seen_keys:
                self.cache_hits += 1
                log.info("cache_hit", prompt=case["prompt"], original_index=self._seen_keys[key])
            else:
                self.cache_misses += 1
                self._seen_keys[key] = idx

            result = _run_single_test_stateless(
                case, idx,
                self.system.model_name,
                self.system.max_product_states,
            )
            self.results.append(result)

        self._emit_summary()

    # -- parallel run ---------------------------------------------------
    def run_all_tests_parallel(self, num_workers: Optional[int] = None) -> None:
        if not self.system and not self.initialize_system():
            return
        if not self.test_suite:
            log.warning("no_tests_loaded")
            return

        if num_workers is None:
            num_workers = min(multiprocessing.cpu_count(), len(self.test_suite))

        chunk_size = max(1, len(self.test_suite) // num_workers)
        chunks = [self.test_suite[i:i + chunk_size]
                  for i in range(0, len(self.test_suite), chunk_size)]

        log.info("batch_started", total=len(self.test_suite), mode="parallel",
                 workers=num_workers, chunks=len(chunks))

        # Track cache dedup before dispatching
        for idx, case in enumerate(self.test_suite):
            key = _prompt_cache_key(case["prompt"])
            if key in self._seen_keys:
                self.cache_hits += 1
            else:
                self.cache_misses += 1
                self._seen_keys[key] = idx

        with ProcessPoolExecutor(max_workers=num_workers) as pool:
            chunk_args = [
                (chunk, ci, self.system.model_name, self.system.max_product_states)
                for ci, chunk in enumerate(chunks)
            ]
            futures = {pool.submit(_process_chunk, ca): ci for ci, ca in enumerate(chunk_args)}

            for future in as_completed(futures):
                chunk_results = future.result()
                self.results.extend(chunk_results)

        self._emit_summary()

    # -- structured summary ---------------------------------------------
    def _emit_summary(self) -> None:
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == Status.PASS)
        failed = sum(1 for r in self.results if r["status"] == Status.FAIL)
        oracle_failed = sum(1 for r in self.results if r["status"] == Status.ORACLE_FAIL)
        errors = sum(1 for r in self.results if r["status"] == Status.ERROR)
        avg_ms = sum(r["time_ms"] for r in self.results) / total if total else 0

        # Cache metrics
        total_cache_lookups = self.cache_hits + self.cache_misses
        cache_hit_ratio = (self.cache_hits / total_cache_lookups * 100) if total_cache_lookups else 0.0

        log.info(
            "batch_summary",
            total=total,
            passed=passed,
            failed_internal=failed,
            failed_oracle=oracle_failed,
            errors=errors,
            pass_rate=round(passed / total * 100, 2) if total else 0,
            avg_time_ms=round(avg_ms, 2),
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            cache_hit_ratio=round(cache_hit_ratio, 2),
        )

        # Category breakdown
        categories: Dict[str, Dict[str, int]] = {}
        for r in self.results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"pass": 0, "fail": 0, "oracle_fail": 0, "error": 0}
            bucket = {"PASS": "pass", "FAIL": "fail", "ORACLE_FAIL": "oracle_fail"}.get(r["status"], "error")
            categories[cat][bucket] += 1

        for cat, counts in sorted(categories.items()):
            cat_total = sum(counts.values())
            log.info(
                "category_summary",
                category=cat,
                passed=counts["pass"],
                total=cat_total,
                pass_rate=round(counts["pass"] / cat_total * 100, 1) if cat_total else 0,
                oracle_failures=counts["oracle_fail"],
            )

        # Flag oracle failures explicitly
        for r in self.results:
            if r["status"] == Status.ORACLE_FAIL:
                log.warning(
                    "oracle_failure_detected",
                    prompt=r["prompt"],
                    oracle_accept_failures=r.get("oracle_accept_failures", ""),
                    oracle_reject_failures=r.get("oracle_reject_failures", ""),
                )

        # Flag cache regression
        if cache_hit_ratio > 10.0:
            log.warning(
                "cache_regression_alert",
                message="High prompt duplication detected — consider deduplicating test suite",
                cache_hit_ratio=round(cache_hit_ratio, 2),
                duplicate_count=self.cache_hits,
            )

    # -- CSV export -----------------------------------------------------
    def export_csv(self, filepath: str) -> None:
        if not self.results:
            log.warning("export_skipped", reason="no results")
            return
        fieldnames = [
            "prompt", "category", "expected_type", "actual_type", "difficulty",
            "status", "states", "time_ms",
            "internal_validated", "oracle_validated",
            "oracle_accept_failures", "oracle_reject_failures",
            "cache_key", "error",
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.results)
        log.info("results_exported", path=filepath, count=len(self.results))

    # -- failure bank ---------------------------------------------------
    def export_failure_bank(self, filepath: Optional[str] = None) -> None:
        oracle_failures = [r for r in self.results if r["status"] == Status.ORACLE_FAIL]
        if not oracle_failures:
            log.info("failure_bank_empty")
            return

        fp = Path(filepath) if filepath else SCRIPT_DIR / "failed_prompts_bank.csv"
        existing: List[Dict[str, Any]] = []
        if fp.exists():
            with open(fp, "r", encoding="utf-8") as f:
                existing = list(csv.DictReader(f))

        ts = datetime.now().isoformat()
        new_entries: List[Dict[str, Any]] = []
        for r in oracle_failures:
            entry: Dict[str, Any] = {
                "timestamp": ts,
                "prompt": r["prompt"],
                "category": r["category"],
                "expected_type": r["expected_type"],
                "actual_type": r.get("actual_type", ""),
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
    parser = argparse.ArgumentParser(
        description="Batch Verification System for Auto-DFA (structured telemetry)",
    )
    parser.add_argument("--input", "-i", type=str, help="Input CSV file with test cases")
    parser.add_argument("--output", "-o", type=str, help="Output CSV file for results")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers")
    parser.add_argument("--export-failed", action="store_true", help="Export failed DFAs as DOT files")
    parser.add_argument("--save-failures", action="store_true", help="Save Oracle failures to bank")
    parser.add_argument("--failure-bank", type=str, default=None, help="Path to failure bank file")
    args = parser.parse_args()

    log.info("batch_verify_started", timestamp=datetime.now().isoformat(),
             input_file=args.input, parallel=args.parallel)

    verifier = BatchVerifier(export_failed=args.export_failed)

    try:
        verifier.load_tests(args.input)
    except FileNotFoundError as exc:
        log.error("input_file_not_found", error=str(exc))
        return 1

    if args.parallel:
        verifier.run_all_tests_parallel(args.workers)
    else:
        verifier.run_all_tests()

    if args.output:
        verifier.export_csv(args.output)

    if args.save_failures:
        verifier.export_failure_bank(args.failure_bank)

    failed_count = sum(1 for r in verifier.results
                       if r["status"] in (Status.FAIL, Status.ORACLE_FAIL, Status.ERROR))
    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
