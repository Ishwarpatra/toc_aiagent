#!/usr/bin/env python3
"""
Analyst Retraining Script - Failure Bank Operationalization

This script processes the failure bank (failed_prompts_bank.csv) and generates
actionable outputs for improving the AnalystAgent:

1. ORACLE_FAIL (Logic Errors) -> Few-shot examples for system prompt
2. ERROR (Crashes) -> Bug reports for debugging

Usage:
    python retrain_analyst.py [--input failed_prompts_bank.csv] [--output few_shot_examples.jsonl]

Workflow:
    1. Run batch_verify.py with --save-failures to collect failures
    2. Run this script to generate training examples
    3. Paste examples into AnalystAgent's system prompt
    4. Re-run QA pipeline to verify improvement
"""

import sys
import os
import csv
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple
from collections import Counter

SCRIPT_DIR = Path(__file__).parent.resolve()


def load_failure_bank(filepath: Path) -> List[Dict[str, Any]]:
    """Load the failure bank CSV file."""
    if not filepath.exists():
        print(f"[!] Failure bank not found: {filepath}")
        print("    Run: python batch_verify.py --save-failures")
        return []
    
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def categorize_failures(failures: List[Dict[str, Any]]) -> Tuple[List[Dict], List[Dict]]:
    """
    Categorize failures into logic errors vs crashes.
    
    Returns: (oracle_failures, error_crashes)
    """
    oracle_failures = []
    error_crashes = []
    
    for f in failures:
        # Check if it's an oracle failure (logic error) or a crash
        if f.get("oracle_accept_failures") or f.get("oracle_reject_failures"):
            oracle_failures.append(f)
        elif "error" in f.get("error", "").lower() or "exception" in f.get("error", "").lower():
            error_crashes.append(f)
        else:
            # Default to oracle failure if we have the data
            oracle_failures.append(f)
    
    return oracle_failures, error_crashes


def generate_few_shot_example(failure: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a failure into a few-shot example for the AnalystAgent.
    
    The format is designed for easy pasting into the system prompt.
    """
    prompt = failure.get("prompt", "")
    expected_type = failure.get("expected_type", "")
    actual_type = failure.get("actual_type", "")
    category = failure.get("category", "")
    
    # Determine what went wrong
    if "AND" in category or "and" in prompt.lower():
        logic_type = "AND"
    elif "OR" in category or "or" in prompt.lower():
        logic_type = "OR"
    else:
        logic_type = expected_type
    
    # Build the correct interpretation
    example = {
        "role": "example",
        "prompt": prompt,
        "expected_logic_type": expected_type,
        "actual_logic_type": actual_type,
        "category": category,
        "lesson": f"When parsing '{prompt}', correctly identify as {expected_type} operation.",
        "correct_interpretation": {
            "logic_type": logic_type,
            "notes": []
        }
    }
    
    # Add specific lessons based on failure type
    if "STARTS_WITH" in expected_type:
        example["correct_interpretation"]["notes"].append(
            "Look for: 'starts with', 'begins with', 'prefix', 'starting with'"
        )
    if "ENDS_WITH" in expected_type:
        example["correct_interpretation"]["notes"].append(
            "Look for: 'ends with', 'suffix', 'ending with'"
        )
    if "CONTAINS" in expected_type:
        example["correct_interpretation"]["notes"].append(
            "Look for: 'contains', 'includes', 'has substring'"
        )
    if "AND" in expected_type or "and" in prompt.lower():
        example["correct_interpretation"]["notes"].append(
            "AND means BOTH conditions must be satisfied simultaneously."
        )
    if "OR" in expected_type or "or" in prompt.lower():
        example["correct_interpretation"]["notes"].append(
            "OR means EITHER condition is sufficient."
        )
    
    return example


def generate_system_prompt_section(examples: List[Dict[str, Any]], max_examples: int = 5) -> str:
    """
    Generate a formatted section for the AnalystAgent's system prompt.
    """
    if not examples:
        return ""
    
    lines = [
        "# FEW-SHOT EXAMPLES (From Production Failures)",
        "",
        "The following examples show prompts that were previously misinterpreted.",
        "Study them carefully to avoid similar mistakes:",
        "",
    ]
    
    # Select diverse examples
    selected = examples[:max_examples]
    
    for i, ex in enumerate(selected, 1):
        lines.append(f"## Example {i}")
        lines.append(f"**Prompt:** \"{ex['prompt']}\"")
        lines.append(f"**Expected:** {ex['expected_logic_type']}")
        lines.append(f"**Lesson:** {ex['lesson']}")
        if ex["correct_interpretation"]["notes"]:
            lines.append("**Notes:**")
            for note in ex["correct_interpretation"]["notes"]:
                lines.append(f"  - {note}")
        lines.append("")
    
    return "\n".join(lines)


def export_jsonl(examples: List[Dict[str, Any]], filepath: Path) -> None:
    """Export examples in JSONL format for fine-tuning or loading."""
    with open(filepath, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"[+] Exported {len(examples)} examples to: {filepath}")


def export_markdown(examples: List[Dict[str, Any]], filepath: Path) -> None:
    """Export examples as Markdown for documentation."""
    content = generate_system_prompt_section(examples, max_examples=len(examples))
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Analyst Training Examples\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("---\n\n")
        f.write(content)
    
    print(f"[+] Exported Markdown to: {filepath}")


def print_summary(failures: List[Dict[str, Any]], oracle_failures: List[Dict], error_crashes: List[Dict]) -> None:
    """Print summary statistics about the failure bank."""
    print("\n" + "=" * 60)
    print("  FAILURE BANK ANALYSIS")
    print("=" * 60)
    
    print(f"\n  Total Failures:        {len(failures)}")
    print(f"  Logic Errors (Oracle): {len(oracle_failures)}")
    print(f"  Crashes (Error):       {len(error_crashes)}")
    
    # Category breakdown
    if oracle_failures:
        print("\n  LOGIC ERRORS BY CATEGORY:")
        categories = Counter(f.get("category", "Unknown") for f in oracle_failures)
        for cat, count in categories.most_common(10):
            print(f"    - {cat}: {count}")
    
    # Expected type breakdown
    if oracle_failures:
        print("\n  MOST CONFUSED OPERATION TYPES:")
        expected = Counter(f.get("expected_type", "Unknown") for f in oracle_failures)
        for exp_type, count in expected.most_common(5):
            print(f"    - {exp_type}: {count} misinterpretations")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Process Failure Bank and Generate Training Examples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python retrain_analyst.py                           Process default failure bank
  python retrain_analyst.py --output examples.jsonl   Export to custom file
  python retrain_analyst.py --markdown                Also export as Markdown

Workflow:
  1. Run batch_verify.py with --save-failures to collect failures
  2. Run this script to generate training examples
  3. Copy examples into AnalystAgent's system prompt
  4. Re-run QA pipeline to verify improvement

Output:
  - few_shot_examples.jsonl: JSONL file for programmatic use
  - training_examples.md: Markdown for documentation/review
  - Console: Summary statistics and copy-paste ready section
        """
    )
    parser.add_argument("--input", "-i", type=str, default="failed_prompts_bank.csv",
                        help="Input failure bank CSV file")
    parser.add_argument("--output", "-o", type=str, default="few_shot_examples.jsonl",
                        help="Output JSONL file for training examples")
    parser.add_argument("--markdown", "-m", action="store_true",
                        help="Also export as Markdown file")
    parser.add_argument("--max-examples", type=int, default=10,
                        help="Maximum examples to include in system prompt section")
    args = parser.parse_args()
    
    # Resolve paths
    input_path = SCRIPT_DIR / args.input if not Path(args.input).is_absolute() else Path(args.input)
    output_path = SCRIPT_DIR / args.output if not Path(args.output).is_absolute() else Path(args.output)
    
    print("\n" + "=" * 60)
    print("  ANALYST RETRAINING SCRIPT")
    print("  Operationalizing the Failure Bank")
    print("=" * 60)
    print(f"\n  Input:  {input_path}")
    print(f"  Output: {output_path}")
    
    # Load failures
    failures = load_failure_bank(input_path)
    
    if not failures:
        print("\n[!] No failures to process.")
        print("    Run the QA pipeline first to collect failures:")
        print("    python batch_verify.py --input tests.csv --save-failures")
        return 1
    
    # Categorize
    oracle_failures, error_crashes = categorize_failures(failures)
    
    # Print summary
    print_summary(failures, oracle_failures, error_crashes)
    
    # Generate examples from oracle failures (logic errors)
    if oracle_failures:
        examples = [generate_few_shot_example(f) for f in oracle_failures]
        
        # Export JSONL
        export_jsonl(examples, output_path)
        
        # Export Markdown if requested
        if args.markdown:
            md_path = output_path.with_suffix(".md")
            export_markdown(examples, md_path)
        
        # Print copy-paste ready section
        print("\n" + "=" * 60)
        print("  COPY-PASTE INTO AnalystAgent SYSTEM PROMPT:")
        print("=" * 60)
        print()
        print(generate_system_prompt_section(examples, max_examples=args.max_examples))
        
        print("=" * 60)
        print("  NEXT STEPS:")
        print("=" * 60)
        print("  1. Copy the above section into agents.py -> AnalystAgent system prompt")
        print("  2. Re-run: python run_qa_pipeline.py --count 100")
        print("  3. Compare ORACLE_FAIL counts before vs after")
        print("  4. Iterate until failures are minimized")
        print("=" * 60 + "\n")
    
    # Report crashes separately
    if error_crashes:
        print("\n[!] CRASH ERRORS (Require Code Fixes):")
        for crash in error_crashes[:5]:
            print(f"    - {crash.get('prompt', 'Unknown')[:50]}...")
            print(f"      Error: {crash.get('error', 'No error message')[:80]}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
