#!/usr/bin/env python3
"""
Automated QA Pipeline Runner for Auto-DFA

This script orchestrates the full QA pipeline:
1. Generate test cases with Oracle Logic
2. Run batch verification with Black Box testing
3. Produce comprehensive pass/fail reports

IMPROVEMENTS:
- Uses pathlib for robust path handling
- Imports functions directly instead of spawning subprocesses where possible
- Better error handling and reporting

Usage:
    python run_qa_pipeline.py [--full] [--count 1000]

Options:
    --full          Run full pipeline with all test types
    --count N       Number of tests to generate (default: 100)
    --output-dir    Directory for output files (default: qa_output)
    --skip-gen      Skip test generation, use existing tests file
"""

import sys
import os
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional

# Setup paths properly using pathlib
SCRIPT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = SCRIPT_DIR.parent / "python_imply"

# Add to path for imports
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(SCRIPT_DIR))


def run_command(cmd: list, cwd: Path = None, timeout: int = 600) -> Tuple[bool, str]:
    """
    Run a command and return (success, output).
    
    Uses proper path handling and increased timeout for large test suites.
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout} seconds"
    except FileNotFoundError as e:
        return False, f"Command not found: {e}"
    except Exception as e:
        return False, f"Error running command: {str(e)}"


def run_test_generation(output_file: Path, count: int = 100) -> Tuple[bool, str]:
    """
    Run test generation as a subprocess.
    
    We use subprocess here because generate_tests.py may take a while
    and we want to show progress.
    """
    gen_script = SCRIPT_DIR / "generate_tests.py"
    
    if not gen_script.exists():
        return False, f"Generate script not found: {gen_script}"
    
    cmd = [
        sys.executable, 
        str(gen_script),
        "--output", str(output_file),
        "--count", str(count)
    ]
    
    print(f"    Command: {' '.join(cmd)}")
    return run_command(cmd, cwd=SCRIPT_DIR)


def run_batch_verification(input_file: Path, output_file: Path, verbose: bool = False) -> Tuple[bool, str]:
    """
    Run batch verification as a subprocess.
    """
    verify_script = SCRIPT_DIR / "batch_verify.py"
    
    if not verify_script.exists():
        return False, f"Verify script not found: {verify_script}"
    
    cmd = [
        sys.executable,
        str(verify_script),
        "--input", str(input_file),
        "--output", str(output_file),
        "--no-color"
    ]
    
    if verbose:
        cmd.append("--verbose")
    
    print(f"    Command: {' '.join(cmd)}")
    
    # Longer timeout for batch verification
    return run_command(cmd, cwd=SCRIPT_DIR, timeout=1800)


def parse_results_csv(results_file: Path) -> dict:
    """Parse results CSV and return summary statistics."""
    import csv
    
    stats = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "oracle_failed": 0,
        "errors": 0,
        "pass_rate": 0.0,
        "categories": {}
    }
    
    if not results_file.exists():
        return stats
    
    with open(results_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        results = list(reader)
    
    stats["total"] = len(results)
    
    for r in results:
        status = r.get("status", "")
        category = r.get("category", "Unknown")
        
        if status == "PASS":
            stats["passed"] += 1
        elif status == "FAIL":
            stats["failed"] += 1
        elif status == "ORACLE_FAIL":
            stats["oracle_failed"] += 1
        else:
            stats["errors"] += 1
        
        if category not in stats["categories"]:
            stats["categories"][category] = {"pass": 0, "fail": 0, "oracle_fail": 0, "error": 0}
        
        if status == "PASS":
            stats["categories"][category]["pass"] += 1
        elif status == "FAIL":
            stats["categories"][category]["fail"] += 1
        elif status == "ORACLE_FAIL":
            stats["categories"][category]["oracle_fail"] += 1
        else:
            stats["categories"][category]["error"] += 1
    
    if stats["total"] > 0:
        stats["pass_rate"] = stats["passed"] / stats["total"] * 100
    
    return stats


def print_category_report(stats: dict) -> None:
    """Print detailed category breakdown."""
    print("\n  CATEGORY BREAKDOWN:")
    print("  " + "-" * 50)
    
    for cat, counts in sorted(stats["categories"].items()):
        total = counts["pass"] + counts["fail"] + counts["oracle_fail"] + counts["error"]
        rate = counts["pass"] / total * 100 if total > 0 else 0
        
        icon = "✓" if counts["fail"] == 0 and counts["oracle_fail"] == 0 and counts["error"] == 0 else "✗"
        print(f"  {icon} {cat:<28} {counts['pass']}/{total} ({rate:.0f}%)")
        
        if counts["oracle_fail"] > 0:
            print(f"      └── Oracle failures: {counts['oracle_fail']}")


def main():
    parser = argparse.ArgumentParser(
        description="Auto-DFA Automated QA Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_qa_pipeline.py                     Quick run with 100 tests
  python run_qa_pipeline.py --count 1000        Run with 1000 tests
  python run_qa_pipeline.py --full              Full pipeline with 6000 tests
  python run_qa_pipeline.py --skip-gen          Use existing test file
        """
    )
    parser.add_argument("--full", action="store_true",
                        help="Run full pipeline (6000 tests)")
    parser.add_argument("--count", type=int, default=100,
                        help="Number of tests to generate (default: 100)")
    parser.add_argument("--output-dir", type=str, default="qa_output",
                        help="Output directory for reports")
    parser.add_argument("--skip-gen", action="store_true",
                        help="Skip test generation, use existing tests file")
    parser.add_argument("--input", type=str, default=None,
                        help="Specific input test file (with --skip-gen)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output during verification")
    args = parser.parse_args()
    
    # Determine test count
    test_count = 6000 if args.full else args.count
    
    # Setup output directory
    output_dir = SCRIPT_DIR / args.output_dir
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tests_file = output_dir / f"tests_{timestamp}.csv"
    results_file = output_dir / f"results_{timestamp}.csv"
    
    # Allow using existing test file
    if args.skip_gen:
        if args.input:
            tests_file = Path(args.input) if Path(args.input).is_absolute() else SCRIPT_DIR / args.input
        else:
            # Find most recent test file
            test_files = sorted(output_dir.glob("tests_*.csv"), reverse=True)
            if test_files:
                tests_file = test_files[0]
            else:
                print("[!] No existing test file found. Run without --skip-gen first.")
                return 1
    
    # Print header
    print("\n" + "=" * 70)
    print("  AUTO-DFA AUTOMATED QA PIPELINE")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print(f"  Test Count: {test_count}")
    print(f"  Output Directory: {output_dir}")
    print("=" * 70)
    
    # Step 1: Generate Tests
    if not args.skip_gen:
        print("\n[STEP 1] Generating test cases with Oracle Logic...")
        
        success, output = run_test_generation(tests_file, test_count)
        
        if not success:
            print(f"[!] Test generation failed:\n{output}")
            return 1
        
        if not tests_file.exists():
            print(f"[!] Test file was not created: {tests_file}")
            return 1
        
        print("[+] Test generation complete")
        print(f"    Output: {tests_file}")
    else:
        print(f"\n[STEP 1] Skipping generation, using: {tests_file}")
        if not tests_file.exists():
            print(f"[!] Test file not found: {tests_file}")
            return 1
    
    # Step 2: Run Batch Verification
    print("\n[STEP 2] Running batch verification with Oracle testing...")
    
    success, output = run_batch_verification(tests_file, results_file, verbose=args.verbose)
    
    # Step 3: Parse and report results
    print("\n[STEP 3] Analyzing results...")
    
    stats = parse_results_csv(results_file)
    
    # Final Report
    print("\n" + "=" * 70)
    print("  QA PIPELINE RESULTS")
    print("=" * 70)
    print(f"  Tests File:        {tests_file}")
    print(f"  Results File:      {results_file}")
    print(f"  Total Tests:       {stats['total']}")
    print(f"  Passed:            {stats['passed']}")
    print(f"  Failed (Internal): {stats['failed']}")
    print(f"  Failed (Oracle):   {stats['oracle_failed']}  <- Circular validation catches!")
    print(f"  Errors:            {stats['errors']}")
    print(f"  Pass Rate:         {stats['pass_rate']:.1f}%")
    
    # Category breakdown
    if stats["categories"]:
        print_category_report(stats)
    
    print("\n" + "=" * 70)
    
    # Overall status
    total_failures = stats["failed"] + stats["oracle_failed"] + stats["errors"]
    
    if total_failures > 0:
        print("\n[!!] QA PIPELINE FAILED - Check results file for details")
        
        if stats["oracle_failed"] > 0:
            print("\n" + "!" * 70)
            print("  CIRCULAR VALIDATION ISSUES DETECTED!")
            print(f"  {stats['oracle_failed']} tests passed internal validation but failed Oracle testing.")
            print("  This indicates potential misinterpretation of prompts by the Analyst.")
            print("!" * 70)
        
        return 1
    else:
        print("\n[OK] QA PIPELINE PASSED - All tests successful")
        return 0


if __name__ == "__main__":
    sys.exit(main())
