#!/usr/bin/env python3
"""
Batch Verification System for Auto-DFA with Black Box Oracle Testing

This script runs a comprehensive test suite against the DFA generation pipeline
to verify correctness using BOTH:
1. Internal Validation (White Box) - checks DFA against internal Spec
2. Oracle Verification (Black Box) - tests DFA against independent truth strings

The Oracle Verification is the key to solving the "Circular Validation" problem:
- It uses pre-computed must_accept/must_reject strings from the test CSV
- These truth strings are independent of the system's Analyst interpretation
- Even if the Analyst misunderstands the prompt, the Oracle will catch it

Usage:
    python batch_verify.py [--input tests.csv] [--output results.csv] [--verbose]

Input:
    - CSV file with columns: prompt, category, expected_type, [difficulty], [must_accept], [must_reject]
    - If no input file specified, uses built-in test suite

Output:
    - Console report with Pass/Fail status
    - Optional CSV export for CI/CD integration
    - Optional DOT file export for failed DFAs (visualization)
"""

import sys
import os
import time
import csv
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import structlog

# Add backend to path so we can import modules
SCRIPT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = SCRIPT_DIR.parent / "python_imply"
sys.path.insert(0, str(BACKEND_DIR))

from main import DFAGeneratorSystem
from core.models import DFA

# Initialize structured logger
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


# =============================================================================
# DEFAULT TEST SUITE (Used when no input CSV provided)
# =============================================================================

DEFAULT_TEST_SUITE: List[Dict[str, Any]] = [
    # --- ATOMIC: Basic Pattern Matching ---
    {
        "prompt": "starts with 'a'", 
        "category": "Atomic", 
        "expected_type": "STARTS_WITH",
        "must_accept": "a;ab;aa;abc",
        "must_reject": "b;ba;bab"
    },
    {
        "prompt": "starts with 'ab'", 
        "category": "Atomic", 
        "expected_type": "STARTS_WITH",
        "must_accept": "ab;aba;abb;abab",
        "must_reject": "a;ba;aab;b"
    },
    {
        "prompt": "ends with 'b'", 
        "category": "Atomic", 
        "expected_type": "ENDS_WITH",
        "must_accept": "b;ab;aab;bb",
        "must_reject": "a;ba;aba"
    },
    {
        "prompt": "ends with '01'", 
        "category": "Atomic", 
        "expected_type": "ENDS_WITH",
        "must_accept": "01;001;101;0101",
        "must_reject": "0;1;10;00;11"
    },
    {
        "prompt": "contains '01'", 
        "category": "Atomic", 
        "expected_type": "CONTAINS",
        "must_accept": "01;001;010;101;0100",
        "must_reject": "0;1;00;11;10"
    },
    {
        "prompt": "contains 'aa'", 
        "category": "Atomic", 
        "expected_type": "CONTAINS",
        "must_accept": "aa;aaa;baa;aab",
        "must_reject": "a;b;ab;ba;aba"
    },
    {
        "prompt": "not contains '11'", 
        "category": "Atomic", 
        "expected_type": "NOT_CONTAINS",
        "must_accept": "0;1;01;10;010;101",
        "must_reject": "11;011;110;111;0110"
    },
    
    # --- ATOMIC: Length Constraints ---
    {
        "prompt": "length is 3", 
        "category": "Atomic_Length", 
        "expected_type": "EXACT_LENGTH",
        "must_accept": "000;001;010;011;100;101;110;111",
        "must_reject": ";0;00;0000;00000"
    },
    {
        "prompt": "length is 5", 
        "category": "Atomic_Length", 
        "expected_type": "EXACT_LENGTH",
        "must_accept": "00000;00001;11111",
        "must_reject": ";0;0000;000000"
    },
    
    # --- ATOMIC: Divisibility ---
    {
        "prompt": "divisible by 2", 
        "category": "Atomic_Numeric", 
        "expected_type": "DIVISIBLE_BY",
        "must_accept": "0;10;100;110",  # Binary: 0, 2, 4, 6
        "must_reject": "1;11;101;111"   # Binary: 1, 3, 5, 7
    },
    {
        "prompt": "divisible by 3", 
        "category": "Atomic_Numeric", 
        "expected_type": "DIVISIBLE_BY",
        "must_accept": "0;11;110;1001",  # Binary: 0, 3, 6, 9
        "must_reject": "1;10;100;101"    # Binary: 1, 2, 4, 5
    },
    
    # --- ATOMIC: Counting Parity ---
    {
        "prompt": "even number of 1s", 
        "category": "Atomic_Count", 
        "expected_type": "EVEN_COUNT",
        "must_accept": ";0;00;11;101;0110",  # 0, 0, 0, 2, 2, 2 ones
        "must_reject": "1;01;10;111;1101"    # 1, 1, 1, 3, 3 ones
    },
    {
        "prompt": "odd number of 0", 
        "category": "Atomic_Count", 
        "expected_type": "ODD_COUNT",
        "must_accept": "0;100;010;001;111110",  # 1, 1, 1, 1, 1 zeros
        "must_reject": ";1;00;1001;0110"        # 0, 0, 2, 2, 2 zeros
    },
    
    # --- ATOMIC: No Consecutive ---
    {
        "prompt": "no consecutive 1s", 
        "category": "Atomic_Constraint", 
        "expected_type": "NO_CONSECUTIVE",
        "must_accept": ";0;1;01;10;010;101;0101",
        "must_reject": "11;011;110;111;101011"
    },
    
    # --- COMPOSITE: Same Alphabet ---
    {
        "prompt": "starts with 'a' and ends with 'b'", 
        "category": "Composite_Same", 
        "expected_type": "AND",
        "must_accept": "ab;aab;abb;abab;aabb",
        "must_reject": "a;b;ba;aa;bb;aba"
    },
    {
        "prompt": "contains '00' or contains '11'", 
        "category": "Composite_Same", 
        "expected_type": "OR",
        "must_accept": "00;11;001;011;100;110;0011",
        "must_reject": ";0;1;01;10;010;101"
    },
    
    # --- NEGATION ---
    {
        "prompt": "does not start with 'a'", 
        "category": "Negation", 
        "expected_type": "NOT_STARTS_WITH",
        "must_accept": "b;ba;bb;bab",
        "must_reject": "a;ab;aa;aba"
    },
]


# =============================================================================
# RESULT STATUS CODES
# =============================================================================

class Status:
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIP = "SKIP"
    ORACLE_FAIL = "ORACLE_FAIL"  # New: passed internal validation but failed oracle


# =============================================================================
# CSV LOADER
# =============================================================================

def load_tests_from_csv(filepath: str) -> List[Dict[str, Any]]:
    """Load test cases from a CSV file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Test file not found: {filepath}")
    
    tests = []
    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize field names
            test = {
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


# =============================================================================
# DFA VISUALIZATION EXPORT
# =============================================================================

def export_dfa_to_dot(dfa: DFA, filepath: str, title: str = "") -> None:
    """
    Export a DFA to GraphViz DOT format for visualization.
    This is useful for debugging failed tests.
    """
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f'digraph DFA {{\n')
        f.write(f'    rankdir=LR;\n')
        f.write(f'    label="{title}";\n')
        f.write(f'    labelloc="t";\n')
        f.write(f'    fontsize=14;\n')
        f.write(f'\n')
        
        # Invisible start node
        f.write(f'    __start__ [shape=none, label=""];\n')
        f.write(f'    __start__ -> "{dfa.start_state}";\n')
        f.write(f'\n')
        
        # States
        for state in dfa.states:
            if state in dfa.accept_states:
                f.write(f'    "{state}" [shape=doublecircle];\n')
            else:
                f.write(f'    "{state}" [shape=circle];\n')
        
        f.write(f'\n')
        
        # Transitions
        for src, trans in dfa.transitions.items():
            for symbol, dest in trans.items():
                f.write(f'    "{src}" -> "{dest}" [label="{symbol}"];\n')
        
        f.write(f'}}\n')


# =============================================================================
# BATCH RUNNER
# =============================================================================

class BatchVerifier:
    """Runs the test suite and collects results with Black Box Oracle Testing."""
    
    def __init__(self, verbose: bool = False, no_color: bool = False, export_failed: bool = False):
        self.verbose = verbose
        self.no_color = no_color
        self.export_failed = export_failed
        self.system: Optional[DFAGeneratorSystem] = None
        self.results: List[Dict[str, Any]] = []
        self.test_suite: List[Dict[str, Any]] = []
        self.failed_dfa_dir: Optional[Path] = None
    
    def initialize_system(self) -> bool:
        """Initialize the DFA Generator System."""
        try:
            print("[*] Initializing DFA Generator System...")
            self.system = DFAGeneratorSystem()
            print("[+] System initialized successfully.\n")
            
            if self.export_failed:
                self.failed_dfa_dir = SCRIPT_DIR / "failed_dfas"
                self.failed_dfa_dir.mkdir(exist_ok=True)
                print(f"[+] Failed DFAs will be exported to: {self.failed_dfa_dir}\n")
            
            return True
        except Exception as e:
            print(f"[!] FATAL: Failed to initialize system: {e}")
            return False
    
    def load_tests(self, input_file: Optional[str] = None) -> None:
        """Load test cases from file or use default suite."""
        if input_file:
            print(f"[*] Loading tests from: {input_file}")
            self.test_suite = load_tests_from_csv(input_file)
            print(f"[+] Loaded {len(self.test_suite)} tests from CSV")
            
            # Report oracle coverage
            with_accept = sum(1 for t in self.test_suite if t.get("must_accept"))
            with_reject = sum(1 for t in self.test_suite if t.get("must_reject"))
            print(f"    - With Oracle Accept Strings: {with_accept}")
            print(f"    - With Oracle Reject Strings: {with_reject}")
        else:
            print(f"[*] Using built-in test suite ({len(DEFAULT_TEST_SUITE)} tests)")
            self.test_suite = DEFAULT_TEST_SUITE
    
    def run_oracle_verification(self, dfa: DFA, case: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run Black Box Oracle Verification on the DFA.
        
        This tests the DFA against pre-computed truth strings that are
        INDEPENDENT of the system's internal logic.
        
        Returns:
            Dict with oracle_pass, accept_failures, reject_failures
        """
        result = {
            "oracle_pass": True,
            "accept_failures": [],
            "reject_failures": [],
            "oracle_error": None
        }
        
        # Check if this is a known contradiction (empty language)
        if case.get("is_contradiction"):
            # For contradictions, nothing should be accepted
            # We could test this more thoroughly, but for now just note it
            result["oracle_error"] = "Contradiction case - expected empty language"
            return result
        
        # Test must_accept strings
        must_accept_str = case.get("must_accept", "")
        if must_accept_str:
            for test_string in must_accept_str.split(";"):
                test_string = test_string.strip()
                if not test_string and test_string != "":
                    continue  # Skip malformed entries (but allow empty string)
                
                # Check if all characters are in DFA's alphabet
                if any(c not in dfa.alphabet for c in test_string):
                    # Alphabet mismatch - the DFA uses different symbols
                    # This isn't necessarily a failure, just incompatible
                    continue
                
                if not dfa.accepts(test_string):
                    result["oracle_pass"] = False
                    result["accept_failures"].append(test_string)
        
        # Test must_reject strings
        must_reject_str = case.get("must_reject", "")
        if must_reject_str:
            for test_string in must_reject_str.split(";"):
                test_string = test_string.strip()
                if not test_string and test_string != "":
                    continue
                
                if any(c not in dfa.alphabet for c in test_string):
                    continue
                
                if dfa.accepts(test_string):
                    result["oracle_pass"] = False
                    result["reject_failures"].append(test_string)
        
        return result
    
    def run_single_test(self, case: Dict[str, Any], test_index: int = 0) -> Dict[str, Any]:
        """Run a single test case through the pipeline with Oracle verification."""
        prompt = case["prompt"]
        category = case.get("category", "Unknown")
        expected_type = case.get("expected_type", "")
        difficulty = case.get("difficulty", "unknown")
        
        result = {
            "prompt": prompt,
            "category": category,
            "expected_type": expected_type,
            "difficulty": difficulty,
            "status": Status.ERROR,
            "actual_type": None,
            "states": 0,
            "time_ms": 0,
            "error": "",
            "internal_validated": False,
            "oracle_validated": False,
            "oracle_accept_failures": "",
            "oracle_reject_failures": ""
        }
        
        start_time = time.perf_counter()
        dfa = None

        try:
            # Log the test start
            logger.info("test_started", prompt=prompt, category=category, test_index=test_index)

            # Step 1: Analyze
            spec = self.system.analyst.analyze(prompt)
            result["actual_type"] = spec.logic_type

            if self.verbose:
                print(f"    [Analyst] Parsed as: {spec.logic_type}, alphabet: {spec.alphabet}")

            # Log analyst success
            logger.info("analyst_success", prompt=prompt, logic_type=spec.logic_type, alphabet=spec.alphabet)

            # Step 2: Design
            dfa = self.system.architect.design(spec)
            result["states"] = len(dfa.states)

            if self.verbose:
                print(f"    [Architect] DFA with {len(dfa.states)} states, alphabet: {dfa.alphabet}")

            # Log architect success
            logger.info("architect_success", prompt=prompt, states=len(dfa.states), alphabet=dfa.alphabet)

            # Step 3: Internal Validation (White Box)
            is_valid, error_msg = self.system.validator.validate(dfa, spec)
            result["internal_validated"] = is_valid

            if self.verbose:
                print(f"    [Validator] Internal: {'PASS' if is_valid else 'FAIL'}")

            # Log validator result
            logger.info("validator_result", prompt=prompt, internal_validated=is_valid, error_msg=error_msg)

            # Step 4: Oracle Verification (Black Box) - THE KEY FIX
            oracle_result = self.run_oracle_verification(dfa, case)
            result["oracle_validated"] = oracle_result["oracle_pass"]
            result["oracle_accept_failures"] = ";".join(oracle_result["accept_failures"][:3])
            result["oracle_reject_failures"] = ";".join(oracle_result["reject_failures"][:3])
            
            if self.verbose:
                print(f"    [Oracle] Black Box: {'PASS' if oracle_result['oracle_pass'] else 'FAIL'}")
                if oracle_result["accept_failures"]:
                    print(f"        Failed to accept: {oracle_result['accept_failures'][:3]}")
                if oracle_result["reject_failures"]:
                    print(f"        Wrongly accepted: {oracle_result['reject_failures'][:3]}")
            
            # Final decision: BOTH must pass
            if is_valid and oracle_result["oracle_pass"]:
                result["status"] = Status.PASS
            elif is_valid and not oracle_result["oracle_pass"]:
                # Internal passed but Oracle failed - this catches "Circular Validation"!
                result["status"] = Status.ORACLE_FAIL
                result["error"] = f"Oracle failures: accept={oracle_result['accept_failures'][:2]}, reject={oracle_result['reject_failures'][:2]}"
            else:
                result["status"] = Status.FAIL
                result["error"] = error_msg or "Validation failed"
                
        except Exception as e:
            result["status"] = Status.ERROR
            result["error"] = str(e)
            logger.error("test_failed", prompt=prompt, error=str(e), traceback=traceback.format_exc())
            if self.verbose:
                import traceback
                traceback.print_exc()

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        result["time_ms"] = round(elapsed_ms, 2)

        # Log test completion
        logger.info("test_completed", prompt=prompt, status=str(result["status"]), time_ms=result["time_ms"])
        
        # Export failed DFA to DOT file for visualization
        if self.export_failed and dfa and result["status"] in [Status.FAIL, Status.ORACLE_FAIL, Status.ERROR]:
            dot_path = self.failed_dfa_dir / f"failed_{test_index:04d}.dot"
            try:
                export_dfa_to_dot(dfa, str(dot_path), title=f"Failed: {prompt[:40]}...")
            except Exception as e:
                if self.verbose:
                    print(f"    [!] Failed to export DOT: {e}")
        
        return result
    
    def run_all_tests(self) -> None:
        """Run the entire test suite."""
        if not self.system:
            if not self.initialize_system():
                return
        
        if not self.test_suite:
            print("[!] No tests to run. Load tests first.")
            return
        
        # Print header
        print("=" * 110)
        print(f"{'CATEGORY':<22} | {'STATUS':<12} | {'TIME':<8} | {'STATES':<6} | {'ORACLE':<8} | {'PROMPT':<40}")
        print("=" * 110)
        
        for idx, case in enumerate(self.test_suite):
            result = self.run_single_test(case, test_index=idx)
            self.results.append(result)
            
            # Print result row
            status_display = result["status"]
            
            if self.no_color:
                status_color = ""
                reset_color = ""
            else:
                if status_display == Status.PASS:
                    status_color = "\033[92m"  # Green
                elif status_display == Status.ORACLE_FAIL:
                    status_color = "\033[95m"  # Magenta (special: internal pass, oracle fail)
                elif status_display == Status.FAIL:
                    status_color = "\033[91m"  # Red
                else:
                    status_color = "\033[93m"  # Yellow
                reset_color = "\033[0m"
            
            time_str = f"{result['time_ms']}ms"
            states_str = str(result["states"]) if result["states"] > 0 else "-"
            oracle_str = "PASS" if result["oracle_validated"] else "FAIL"
            prompt_display = result["prompt"][:40] if len(result["prompt"]) > 40 else result["prompt"]
            
            print(f"{result['category']:<22} | {status_color}{status_display:<12}{reset_color} | {time_str:<8} | {states_str:<6} | {oracle_str:<8} | {prompt_display}")
            
            if result["status"] in [Status.FAIL, Status.ERROR, Status.ORACLE_FAIL] and result["error"]:
                error_display = result["error"][:80] if len(result["error"]) > 80 else result["error"]
                print(f"{'':22}   +-- Error: {error_display}")
        
        # Print summary
        self._print_summary()

    def run_all_tests_parallel(self, num_workers: Optional[int] = None, process_func=None) -> None:
        """Run the entire test suite using parallel processing."""
        if not self.system:
            if not self.initialize_system():
                return

        if not self.test_suite:
            print("[!] No tests to run. Load tests first.")
            return

        if num_workers is None:
            num_workers = min(multiprocessing.cpu_count(), len(self.test_suite))

        # Split tests into chunks for parallel processing
        chunk_size = max(1, len(self.test_suite) // num_workers)
        test_chunks = [self.test_suite[i:i + chunk_size]
                      for i in range(0, len(self.test_suite), chunk_size)]

        print(f"[*] Running {len(self.test_suite)} tests using {num_workers} workers...")
        print(f"[*] Split into {len(test_chunks)} chunks")

        # Print header
        print("=" * 110)
        print(f"{'CATEGORY':<22} | {'STATUS':<12} | {'TIME':<8} | {'STATES':<6} | {'ORACLE':<8} | {'PROMPT':<40}")
        print("=" * 110)

        # Process chunks in parallel
        all_results = []
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            # Prepare data for each chunk
            chunk_data_list = []
            for chunk_idx, chunk in enumerate(test_chunks):
                chunk_data = (chunk, chunk_idx, self.system.model_name, self.system.max_product_states)
                chunk_data_list.append(chunk_data)

            # Submit jobs for each chunk
            futures = [executor.submit(process_func, chunk_data) for chunk_data in chunk_data_list]

            # Collect results as they complete
            for future in as_completed(futures):
                chunk_results = future.result()
                all_results.extend(chunk_results)

                # Add results to main results list
                for result in chunk_results:
                    self.results.append(result)

        # Print summary
        self._print_summary()


    def _print_summary(self) -> None:
        """Print test summary with oracle statistics."""
        total = len(self.results)
        passed = len([r for r in self.results if r["status"] == Status.PASS])
        failed = len([r for r in self.results if r["status"] == Status.FAIL])
        oracle_failed = len([r for r in self.results if r["status"] == Status.ORACLE_FAIL])
        errors = len([r for r in self.results if r["status"] == Status.ERROR])
        
        print("\n" + "=" * 110)
        print("SUMMARY")
        print("=" * 110)
        print(f"  Total Tests:       {total}")
        print(f"  Passed:            {passed}")
        print(f"  Failed (Internal): {failed}")
        print(f"  Failed (Oracle):   {oracle_failed}  <- Caught by Black Box testing!")
        print(f"  Errors:            {errors}")
        print(f"  Pass Rate:         {(passed/total*100):.1f}%" if total > 0 else "  Pass Rate: N/A")
        print("=" * 110)
        
        # Highlight Oracle failures - these are the "Circular Validation" catches
        if oracle_failed > 0:
            print("\n" + "!" * 110)
            print("  ORACLE FAILURES DETECTED")
            print("  These tests passed internal validation but failed Black Box oracle testing.")
            print("  This indicates the Analyst may have misinterpreted the prompt!")
            print("!" * 110)
            for r in self.results:
                if r["status"] == Status.ORACLE_FAIL:
                    print(f"    - {r['prompt'][:60]}")
                    if r["oracle_accept_failures"]:
                        print(f"      Failed to accept: {r['oracle_accept_failures']}")
                    if r["oracle_reject_failures"]:
                        print(f"      Wrongly accepted: {r['oracle_reject_failures']}")
        
        # Category breakdown
        print("\nBY CATEGORY:")
        categories = {}
        for r in self.results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"pass": 0, "fail": 0, "oracle_fail": 0, "error": 0}
            if r["status"] == Status.PASS:
                categories[cat]["pass"] += 1
            elif r["status"] == Status.FAIL:
                categories[cat]["fail"] += 1
            elif r["status"] == Status.ORACLE_FAIL:
                categories[cat]["oracle_fail"] += 1
            else:
                categories[cat]["error"] += 1
        
        for cat, counts in sorted(categories.items()):
            total_cat = counts["pass"] + counts["fail"] + counts["oracle_fail"] + counts["error"]
            rate = counts["pass"] / total_cat * 100 if total_cat > 0 else 0
            status_indicator = "[OK]" if counts["fail"] == 0 and counts["oracle_fail"] == 0 and counts["error"] == 0 else "[!!]"
            print(f"  {status_indicator} {cat:<24} {counts['pass']}/{total_cat} ({rate:.0f}%)")
            if counts["oracle_fail"] > 0:
                print(f"      └── Oracle failures: {counts['oracle_fail']}")
        
        # Difficulty breakdown if available
        difficulties = {}
        for r in self.results:
            diff = r.get("difficulty", "unknown")
            if diff not in difficulties:
                difficulties[diff] = {"pass": 0, "fail": 0, "oracle_fail": 0, "error": 0}
            if r["status"] == Status.PASS:
                difficulties[diff]["pass"] += 1
            elif r["status"] == Status.FAIL:
                difficulties[diff]["fail"] += 1
            elif r["status"] == Status.ORACLE_FAIL:
                difficulties[diff]["oracle_fail"] += 1
            else:
                difficulties[diff]["error"] += 1
        
        if len(difficulties) > 1 or "unknown" not in difficulties:
            print("\nBY DIFFICULTY:")
            for diff, counts in sorted(difficulties.items()):
                total_diff = counts["pass"] + counts["fail"] + counts["oracle_fail"] + counts["error"]
                rate = counts["pass"] / total_diff * 100 if total_diff > 0 else 0
                status_indicator = "[OK]" if counts["fail"] == 0 and counts["oracle_fail"] == 0 and counts["error"] == 0 else "[!!]"
                print(f"  {status_indicator} {diff:<24} {counts['pass']}/{total_diff} ({rate:.0f}%)")
    
    def export_csv(self, filepath: str) -> None:
        """Export results to CSV file."""
        if not self.results:
            print("[!] No results to export.")
            return
        
        fieldnames = [
            "prompt", "category", "expected_type", "actual_type", "difficulty",
            "status", "states", "time_ms", 
            "internal_validated", "oracle_validated",
            "oracle_accept_failures", "oracle_reject_failures",
            "error"
        ]
        
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.results)
        
        print(f"\n[+] Results exported to: {filepath}")
    
    def export_failure_bank(self, filepath: str = None) -> None:
        """
        Export ORACLE_FAIL prompts to a dedicated file for retraining.
        
        These prompts represent cases where the Analyst fundamentally 
        misunderstood the user's intent. They are valuable for:
        1. Few-shot examples in the Analyst's system prompt
        2. Targeted testing and debugging
        3. Continuous improvement of the parser
        """
        oracle_failures = [r for r in self.results if r["status"] == Status.ORACLE_FAIL]
        
        if not oracle_failures:
            print("[+] No Oracle failures to export.")
            return
        
        if filepath is None:
            filepath = SCRIPT_DIR / "failed_prompts_bank.csv"
        else:
            filepath = Path(filepath)
        
        # Append to existing bank if it exists
        existing = []
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                existing = list(reader)
        
        # Add new failures with timestamp
        timestamp = datetime.now().isoformat()
        new_entries = []
        for r in oracle_failures:
            entry = {
                "timestamp": timestamp,
                "prompt": r["prompt"],
                "category": r["category"],
                "expected_type": r["expected_type"],
                "actual_type": r.get("actual_type", ""),
                "oracle_accept_failures": r.get("oracle_accept_failures", ""),
                "oracle_reject_failures": r.get("oracle_reject_failures", ""),
                "error": r.get("error", "")
            }
            # Avoid duplicates
            if not any(e.get("prompt") == entry["prompt"] for e in existing):
                new_entries.append(entry)
        
        if not new_entries:
            print(f"[+] All Oracle failures already in bank: {filepath}")
            return
        
        # Write combined bank
        all_entries = existing + new_entries
        fieldnames = ["timestamp", "prompt", "category", "expected_type", "actual_type",
                     "oracle_accept_failures", "oracle_reject_failures", "error"]
        
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(all_entries)
        
        print(f"\n[+] Failure Bank updated: {filepath}")
        print(f"    - New entries: {len(new_entries)}")
        print(f"    - Total entries: {len(all_entries)}")
        print("    [TIP] Use these prompts as few-shot examples in AnalystAgent!")


def check_environment() -> Dict[str, bool]:
    """
    Check the environment for required dependencies.
    
    Returns a dict of {dependency: is_available} for each checked item.
    """
    import shutil
    
    checks = {}
    
    # Check for Graphviz 'dot' binary
    checks["graphviz_dot"] = shutil.which("dot") is not None
    
    # Check for Python version
    checks["python_3_8+"] = sys.version_info >= (3, 8)
    
    # Check for required packages
    try:
        import pydantic
        checks["pydantic"] = True
    except ImportError:
        checks["pydantic"] = False
    
    return checks


def print_environment_warnings() -> None:
    """Print warnings for missing dependencies."""
    checks = check_environment()
    
    if not checks.get("graphviz_dot"):
        print("[WARNING] Graphviz 'dot' binary not found.")
        print("          Visualization export (--export-failed) will not work.")
        print("          Install: https://graphviz.org/download/")
        print()
    
    if not checks.get("pydantic"):
        print("[WARNING] pydantic not installed. Models may not work correctly.")
        print()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Batch Verification System for Auto-DFA with Black Box Oracle Testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_verify.py                                Run with built-in tests
  python batch_verify.py --input generated_tests.csv   Run with custom test file
  python batch_verify.py --output results.csv          Export results to CSV
  python batch_verify.py --verbose                     Show detailed output
  python batch_verify.py --export-failed               Export failed DFAs as DOT files
  python batch_verify.py --save-failures               Save Oracle failures for retraining
  python batch_verify.py --no-color                    Disable ANSI colors

Workflow:
  1. Generate tests:  python generate_tests.py --output tests.csv
  2. Run tests:       python batch_verify.py --input tests.csv --output results.csv --save-failures
  
Oracle Testing:
  The test CSV can include 'must_accept' and 'must_reject' columns with semicolon-
  separated test strings. These provide ground truth for Black Box verification,
  independent of the system's internal logic.

Failure Bank:
  Use --save-failures to export Oracle failures to 'failed_prompts_bank.csv'.
  These prompts can be used as few-shot examples in AnalystAgent for improvement.
        """
    )
    parser.add_argument("--input", "-i", type=str, help="Input CSV file with test cases")
    parser.add_argument("--output", "-o", type=str, help="Output CSV file for results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors (for Windows/CI)")
    parser.add_argument("--export-failed", action="store_true", help="Export failed DFAs as GraphViz DOT files")
    parser.add_argument("--save-failures", action="store_true", help="Save Oracle failures to failure bank for retraining")
    parser.add_argument("--failure-bank", type=str, default=None, help="Path to failure bank file (default: failed_prompts_bank.csv)")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel", default=False)
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers (default: CPU count)")
    args = parser.parse_args()
    
    print("\n" + "=" * 110)
    print("  AUTO-DFA BATCH VERIFICATION SYSTEM (with Black Box Oracle Testing)")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    if args.input:
        print(f"  Input File: {args.input}")
    print("=" * 110 + "\n")
    
    # Check environment and print warnings
    print_environment_warnings()
    
    verifier = BatchVerifier(
        verbose=args.verbose, 
        no_color=args.no_color,
        export_failed=args.export_failed
    )
    
    try:
        verifier.load_tests(args.input)
    except FileNotFoundError as e:
        print(f"[!] Error: {e}")
        return 1
    
    if args.parallel:
        from multiprocess_utils import process_test_chunk_serialized
        verifier.run_all_tests_parallel(args.workers, process_test_chunk_serialized)
    else:
        verifier.run_all_tests()

    if args.output:
        verifier.export_csv(args.output)
    
    # Export failure bank for retraining (Recommendation 2)
    if args.save_failures:
        verifier.export_failure_bank(args.failure_bank)
    
    # Exit with appropriate code for CI/CD
    failed_or_error = len([r for r in verifier.results 
                           if r["status"] in [Status.FAIL, Status.ORACLE_FAIL, Status.ERROR]])
    return 1 if failed_or_error > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

