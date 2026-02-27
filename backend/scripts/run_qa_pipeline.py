#!/usr/bin/env python3
"""
Automated QA Pipeline Runner for Auto-DFA

This script orchestrates the full QA pipeline:
1. Generate test cases with Oracle Logic
2. Run batch verification with Black Box testing
3. Produce comprehensive pass/fail reports

All telemetry emitted as structured JSON via structlog for ELK/Datadog ingestion.

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
from typing import Tuple, Optional, Dict, Any

import structlog

# Setup paths properly using pathlib
SCRIPT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = SCRIPT_DIR.parent / "python_imply"

# Add to path for imports
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(SCRIPT_DIR))

# ---------------------------------------------------------------------------
# Structured logging configuration
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
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()


def run_command(cmd: list, cwd: Path = None, timeout: int = 600, stream_output: bool = False) -> Tuple[bool, str]:
    """
    Run a command and return (success, output).

    Uses proper path handling and increased timeout for large test suites.

    Args:
        cmd: Command and arguments to run
        cwd: Working directory
        timeout: Timeout in seconds
        stream_output: If True, stream stdout/stderr directly to console instead of capturing
    """
    try:
        if stream_output:
            # Stream output directly - critical for debugging initialization failures
            # Output is emitted as JSONL from the subprocess
            result = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                timeout=timeout
            )
            output = ""  # Output already streamed to console
            return result.returncode == 0, output
        else:
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
    """
    gen_script = SCRIPT_DIR / "generate_tests.py"

    if not gen_script.exists():
        log.error("generate_script_not_found", path=str(gen_script))
        return False, f"Generate script not found: {gen_script}"

    cmd = [
        sys.executable,
        str(gen_script),
        "--output", str(output_file),
        "--count", str(count)
    ]

    log.info("test_generation_started", command=" ".join(cmd), output_file=str(output_file), count=count)
    return run_command(cmd, cwd=SCRIPT_DIR)


def run_batch_verification(input_file: Path, output_file: Path, verbose: bool = False) -> Tuple[bool, str]:
    """
    Run batch verification as a subprocess.

    CRITICAL: Streams output directly to console to expose initialization failures
    and schema validation errors that would otherwise be swallowed.
    """
    verify_script = SCRIPT_DIR / "batch_verify.py"

    if not verify_script.exists():
        log.error("verify_script_not_found", path=str(verify_script))
        return False, f"Verify script not found: {verify_script}"

    cmd = [
        sys.executable,
        str(verify_script),
        "--input", str(input_file),
        "--output", str(output_file),
        "--parallel",  # CRITICAL: Enable parallel execution
    ]

    if verbose:
        cmd.append("--verbose")

    log.info("batch_verification_started", command=" ".join(cmd), input_file=str(input_file), output_file=str(output_file))

    # Longer timeout for batch verification
    # CRITICAL: stream_output=True ensures telemetry is never swallowed
    return run_command(cmd, cwd=SCRIPT_DIR, timeout=1800, stream_output=True)


def parse_results_csv(results_file: Path) -> dict:
    """Parse results CSV and return summary statistics."""
    import csv

    stats: Dict[str, Any] = {
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


def log_category_report(stats: dict) -> None:
    """Log detailed category breakdown as structured JSON."""
    for cat, counts in sorted(stats["categories"].items()):
        total = counts["pass"] + counts["fail"] + counts["oracle_fail"] + counts["error"]
        rate = counts["pass"] / total * 100 if total > 0 else 0
        passed = counts["fail"] == 0 and counts["oracle_fail"] == 0 and counts["error"] == 0

        log.info(
            "category_result",
            category=cat,
            passed=counts["pass"],
            total=total,
            pass_rate=round(rate, 1),
            status="PASS" if passed else "FAIL",
            oracle_failures=counts["oracle_fail"],
            timeouts=counts["error"],
        )


def main() -> int:
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
    parser.add_argument("--clear-cache", action="store_true",
                        help="Clear diskcache before running pipeline")
    args = parser.parse_args()

    # Determine test count
    test_count = 6000 if args.full else args.count

    # CRITICAL: Clear cache if requested (use API, not manual file deletion)
    if args.clear_cache:
        try:
            import diskcache as dc
            cache_dir = BACKEND_DIR / ".cache"
            cache_dir.mkdir(exist_ok=True)
            cache = dc.Cache(directory=str(cache_dir))
            cache.clear()
            cache.close()
            log.info("cache_cleared", directory=str(cache_dir))
        except Exception as e:
            log.warning("cache_clear_failed", error=str(e))

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
                log.error("no_existing_test_file", message="No existing test file found. Run without --skip-gen first.")
                return 1

    # Log pipeline start
    log.info(
        "pipeline_started",
        timestamp=datetime.now().isoformat(),
        test_count=test_count,
        output_dir=str(output_dir),
        tests_file=str(tests_file),
        results_file=str(results_file),
        skip_gen=args.skip_gen,
    )

    # Step 1: Generate Tests
    if not args.skip_gen:
        log.info("step_1_test_generation", status="started")

        success, output = run_test_generation(tests_file, test_count)

        if not success:
            log.error("step_1_test_generation", status="failed", error=output)
            return 1

        if not tests_file.exists():
            log.error("step_1_test_generation", status="failed", error="Test file was not created", path=str(tests_file))
            return 1

        log.info("step_1_test_generation", status="completed", path=str(tests_file))
    else:
        log.info("step_1_skipped", using=str(tests_file))
        if not tests_file.exists():
            log.error("test_file_not_found", path=str(tests_file))
            return 1

    # Step 2: Run Batch Verification
    log.info("step_2_batch_verification", status="started")

    success, output = run_batch_verification(tests_file, results_file, verbose=args.verbose)

    # Step 3: Parse and report results
    log.info("step_3_analyzing_results", status="started")

    stats = parse_results_csv(results_file)

    # Final Report
    log.info(
        "pipeline_results",
        tests_file=str(tests_file),
        results_file=str(results_file),
        total_tests=stats["total"],
        passed=stats["passed"],
        failed_internal=stats["failed"],
        failed_oracle=stats["oracle_failed"],
        errors=stats["errors"],
        pass_rate=round(stats["pass_rate"], 1),
    )

    # Category breakdown
    if stats["categories"]:
        log_category_report(stats)

    # Overall status
    total_failures = stats["failed"] + stats["oracle_failed"] + stats["errors"]

    # CRITICAL: Fail if 0 tests were executed (prevents false-positive success)
    if stats["total"] == 0:
        log.error("pipeline_failed", reason="0 tests were executed")
        return 1

    if total_failures > 0:
        log.error(
            "pipeline_failed",
            reason="test_failures",
            total_failures=total_failures,
            oracle_failures=stats["oracle_failed"],
        )

        if stats["oracle_failed"] > 0:
            log.error(
                "circular_validation_issues",
                message="Tests passed internal validation but failed Oracle testing",
                oracle_failed_count=stats["oracle_failed"],
            )

        return 1
    else:
        log.info("pipeline_passed", message="All tests successful")
        return 0


if __name__ == "__main__":
    sys.exit(main())
