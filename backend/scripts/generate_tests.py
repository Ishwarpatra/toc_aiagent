#!/usr/bin/env python3
"""
Test Generator for Auto-DFA QA Pipeline - Large Scale Suite with Oracle Logic

Generates a wide variety of unique test cases covering:
- Atomic patterns (starts_with, ends_with, contains, length, divisibility, parity)
- Composite logic (AND, OR combinations)
- Alphabet clashes (mixing {a,b} with {0,1})
- Negations (not_contains, not_starts_with, not_ends_with)
- Edge cases (single char, long patterns, overlapping patterns)

ENHANCED: Now includes "Oracle Strings" (must_accept, must_reject) for Black Box testing.
These truth strings are generated independently of the system's internal logic,
solving the "Circular Validation" problem.

Usage:
    python generate_tests.py [--output tests.csv] [--count 6000]
"""

import sys
import os
import csv
import argparse
import itertools
import random
import string
from datetime import datetime
from typing import List, Dict, Any, Tuple
import yaml

# Add the backend directory to the path to import core modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import Oracle from the canonical core module — single source of truth
from python_imply.core.oracle import (
    check_condition,
    get_oracle_strings,
    detect_contradiction,
    CompositeOracleSolver,
)

# Seed for reproducibility
random.seed(42)

# Load configuration — all constants driven by config, not hardcoded
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'patterns.yaml')

os.makedirs(CONFIG_DIR, exist_ok=True)

with open(CONFIG_PATH, 'r') as f:
    CONFIG = yaml.safe_load(f)

SYNONYMS = CONFIG['synonyms']
CONTEXT_HEADERS = CONFIG['context_headers']
ALPHABETS = CONFIG['alphabets']
SAFE_AND_COMBINATIONS = CONFIG['safe_combinations']['and']
SAFE_OR_COMBINATIONS = CONFIG['safe_combinations']['or']

# Alphabet pools derived from config — no magic strings
BINARY_CHARS = ALPHABETS['binary']
TERNARY_CHARS = ALPHABETS['ternary']
DECIMAL_CHARS = ALPHABETS['decimal']
HEX_CHARS = ALPHABETS['hex']
LETTER_BINARY_CHARS = ALPHABETS['letter_binary']
LETTER_TERNARY_CHARS = ALPHABETS['letter_ternary']
LETTER_CHARS = list(string.ascii_lowercase[:6])  # a through f
MIXED_CHARS = BINARY_CHARS + LETTER_CHARS


# =============================================================================
# HELPERS
# =============================================================================

def get_random_pattern(chars: List[str], length: int) -> str:
    return "".join(random.choice(chars) for _ in range(length))

def get_random_phrasing(op_type: str, pattern: str) -> str:
    """Get a random phrasing for the given operation type using synonyms from config."""
    if op_type in SYNONYMS:
        phrase_template = random.choice(SYNONYMS[op_type])
        # Format the template with the pattern
        if "'" in phrase_template or '"' in phrase_template:
            # Template already has quotes, just replace the pattern
            return phrase_template.replace("'", "").replace('"', '').replace(pattern, f"'{pattern}'")
        else:
            # Add quotes around the pattern
            return f"{phrase_template} '{pattern}'"
    else:
        return f"{op_type} '{pattern}'"

def get_context_header(alphabet_type: str = None) -> Tuple[str, List[str]]:
    """Generate a context header that specifies the alphabet for the problem."""
    if alphabet_type is None:
        alphabet_type = random.choice(['binary', 'ternary', 'decimal', 'letter_binary'])

    if alphabet_type == 'binary':
        header = random.choice(CONTEXT_HEADERS['binary'])
        return f"In the {header}, ", BINARY_CHARS
    elif alphabet_type == 'ternary':
        header = random.choice(CONTEXT_HEADERS['ternary'])
        return f"In the {header}, ", TERNARY_CHARS
    elif alphabet_type == 'decimal':
        header = random.choice(CONTEXT_HEADERS['decimal'])
        return f"For {header}, ", DECIMAL_CHARS
    elif alphabet_type == 'letter_binary':
        return "For strings over alphabet {a, b}, ", LETTER_BINARY_CHARS
    else:
        return "", BINARY_CHARS

def generate_range_query() -> Tuple[str, List[str], str, str, str, str]:
    """
    Generate a range query that looks atomic but is actually composite.
    Returns: (prompt, alphabet, op1, pat1, op2, pat2)
    """
    # Choose a range type
    range_type = random.choice(['length', 'count'])

    if range_type == 'length':
        # Generate "Length between X and Y" which is MIN_LENGTH X AND MAX_LENGTH Y
        low = random.randint(3, 8)
        high = random.randint(low + 1, low + 5)

        # Create variations of range expressions
        range_exprs = [
            f"length between {low} and {high}",
            f"strings of length from {low} to {high}",
            f"length in range [{low}, {high}]",
            f"length at least {low} and at most {high}",
            f"length no less than {low} and no more than {high}",
            f"length greater than or equal to {low} and less than or equal to {high}"
        ]

        prompt = random.choice(range_exprs)
        return prompt, BINARY_CHARS, "MIN_LENGTH", str(low), "MAX_LENGTH", str(high)

    else:  # count
        # Generate count range query
        char = random.choice(BINARY_CHARS)
        low = random.randint(1, 4)
        high = random.randint(low + 1, low + 3)

        count_exprs = [
            f"strings with number of {char}s between {low} and {high}",
            f"strings having from {low} to {high} {char}s",
            f"count of {char} between {low} and {high}",
            f"number of {char}s in range [{low}, {high}]"
        ]

        prompt = random.choice(count_exprs)
        return prompt, BINARY_CHARS, "EXACT_LENGTH", str(low), "EXACT_LENGTH", str(high)  # Placeholder - should be COUNT related

# =============================================================================
# TEST CASE GENERATORS
# =============================================================================

def generate_atomic_pattern_tests(count: int) -> List[Dict[str, Any]]:
    tests = []
    ops = ["STARTS_WITH", "ENDS_WITH", "CONTAINS", "NOT_CONTAINS", "NOT_STARTS_WITH", "NOT_ENDS_WITH"]

    for _ in range(count):
        op = random.choice(ops)
        # Random character set - now with context-dependent options
        char_set_choice = random.random()
        if char_set_choice < 0.2:  # 20% chance of context header
            context_header, char_set = get_context_header()
            # Generate pattern from the specific alphabet
            length = random.randint(1, 8)
            pattern = get_random_pattern(char_set, length)
            prompt = context_header + get_random_phrasing(op, pattern)
        else:
            # Regular selection without context header
            char_set = random.choice([BINARY_CHARS, LETTER_CHARS[:2], MIXED_CHARS[:4], MIXED_CHARS])
            # Random length 1-8
            length = random.randint(1, 8)
            pattern = get_random_pattern(char_set, length)
            prompt = get_random_phrasing(op, pattern)

        category = "Atomic" if "NOT" not in op else "Negation"

        # Generate oracle strings for Black Box testing
        accept_strs, reject_strs = get_oracle_strings(op, pattern, char_set)

        tests.append({
            "prompt": prompt,
            "category": f"{category}_{op}",
            "expected_type": op,
            "difficulty": "easy" if length <= 2 else ("medium" if length <= 4 else "hard"),
            "must_accept": ";".join(accept_strs),
            "must_reject": ";".join(reject_strs),
            "is_contradiction": "false"
        })
    return tests

def generate_numeric_tests(count: int) -> List[Dict[str, Any]]:
    tests = []
    for _ in range(count):
        # Add range queries as a possibility
        if random.random() < 0.1:  # 10% chance of range query
            prompt, alphabet, op1, pat1, op2, pat2 = generate_range_query()

            # For range queries, we need to generate oracle strings differently
            # For length ranges: strings with length between low and high
            if "length" in prompt.lower():
                # Generate strings that satisfy the length range
                low_len = int(min(pat1, pat2))
                high_len = int(max(pat1, pat2))

                # Generate accept strings with lengths in range
                accept_strs = []
                for length in range(low_len, min(high_len + 1, low_len + 3)):  # Limit to avoid too many
                    accept_strs.append(alphabet[0] * length)

                # Generate reject strings with lengths outside range
                reject_strs = []
                if low_len > 0:
                    reject_strs.append(alphabet[0] * (low_len - 1))
                reject_strs.append(alphabet[0] * (high_len + 1))
            elif "count" in prompt.lower() or "number" in prompt.lower():
                # For count ranges: "count of X between A and B"
                # Extract target symbol and range
                import re
                match = re.search(r"count of ([01ab\d]) between (\d+) and (\d+)", prompt.lower())
                if match:
                    target_sym, low_count, high_count = match.groups()
                    low_count, high_count = int(low_count), int(high_count)

                    # Generate accept strings with count of target symbol in range
                    accept_strs = []
                    for count in range(low_count, high_count + 1):
                        # Create a string with exactly 'count' occurrences of target_sym
                        s = target_sym * count
                        # Fill remaining positions with other symbols to make it interesting
                        other_sym = alphabet[1] if alphabet[0] == target_sym else alphabet[0]
                        s += other_sym * 2  # Add some other symbols
                        accept_strs.append(s)

                    # Generate reject strings with count outside range
                    reject_strs = []
                    if low_count > 0:
                        # Too few occurrences
                        reject_strs.append(target_sym * (low_count - 1) + other_sym * 2)
                    # Too many occurrences
                    reject_strs.append(target_sym * (high_count + 1) + other_sym * 2)
                else:
                    # Fallback if regex doesn't match
                    accept_strs, reject_strs = get_oracle_strings("EXACT_LENGTH", str(5), alphabet)  # Placeholder
            else:
                # For other ranges, use a simpler approach
                accept_strs, reject_strs = get_oracle_strings("EXACT_LENGTH", str(5), alphabet)  # Placeholder

            tests.append({
                "prompt": prompt,
                "category": "Composite_Range",
                "expected_type": "COMPOSITE_RANGE",
                "difficulty": "hard",
                "must_accept": ";".join(accept_strs),
                "must_reject": ";".join(reject_strs),
                "is_contradiction": "false"
            })
        elif random.random() < 0.3:
            # Length with possible context header
            n = random.randint(1, 40)

            # Add context header sometimes
            if random.random() < 0.2:
                context_header, alphabet = get_context_header()
                prompt = context_header + random.choice([f"length is {n}", f"length = {n}", f"exactly {n} characters", f"has length {n}"])
            else:
                prompt = random.choice([f"length is {n}", f"length = {n}", f"exactly {n} characters", f"has length {n}"])
                alphabet = BINARY_CHARS

            # Generate oracle strings
            accept_strs, reject_strs = get_oracle_strings("EXACT_LENGTH", str(n), alphabet)

            tests.append({
                "prompt": prompt,
                "category": "Atomic_Length",
                "expected_type": "EXACT_LENGTH",
                "difficulty": "medium" if n > 10 else "easy",
                "must_accept": ";".join(accept_strs),
                "must_reject": ";".join(reject_strs),
                "is_contradiction": "false"
            })
        else:
            # Divisibility with possible context header
            n = random.randint(2, 50)

            # Add context header sometimes
            if random.random() < 0.2:
                context_header, alphabet = get_context_header()
                prompt = context_header + random.choice([f"divisible by {n}", f"multiple of {n}", f"count mod {n} is 0"])
            else:
                prompt = random.choice([f"divisible by {n}", f"multiple of {n}", f"count mod {n} is 0"])
                alphabet = BINARY_CHARS

            # Generate oracle strings
            accept_strs, reject_strs = get_oracle_strings("DIVISIBLE_BY", str(n), alphabet)

            tests.append({
                "prompt": prompt,
                "category": "Atomic_Numeric",
                "expected_type": "DIVISIBLE_BY",
                "difficulty": "hard" if n > 10 else "medium",
                "must_accept": ";".join(accept_strs),
                "must_reject": ";".join(reject_strs),
                "is_contradiction": "false"
            })
    return tests

def generate_parity_tests(count: int) -> List[Dict[str, Any]]:
    tests = []
    for _ in range(count):
        # Sometimes use context header
        if random.random() < 0.2:
            context_header, alphabet = get_context_header()
            char = random.choice(alphabet)
        else:
            char = random.choice(MIXED_CHARS)
            alphabet = [char, '1' if char == '0' else '0']

        is_even = random.choice([True, False])
        parity = "even" if is_even else "odd"
        op_type = "EVEN_COUNT" if is_even else "ODD_COUNT"

        prompt = random.choice([
            f"{parity} number of {char}s",
            f"{parity} count of {char}",
            f"{parity} number of '{char}'",
            f"count of {char} is {parity}"
        ])

        # Add context header if applicable
        if random.random() < 0.2:
            context_header, _ = get_context_header()
            prompt = context_header + prompt

        # Generate oracle strings
        other = '1' if char == '0' else '0'
        alphabet = [char, other]
        accept_strs, reject_strs = get_oracle_strings(op_type, char, alphabet)

        tests.append({
            "prompt": prompt,
            "category": "Atomic_Count",
            "expected_type": op_type,
            "difficulty": "easy",
            "must_accept": ";".join(accept_strs),
            "must_reject": ";".join(reject_strs),
            "is_contradiction": "false"
        })
    return tests

def generate_composite_tests(count: int) -> List[Dict[str, Any]]:
    tests = []

    # Building blocks for composites - prefer safe combinations
    def get_random_atomic_for_composite(prefer_safe: bool = True) -> Tuple[str, str, str, List[str]]:
        """Returns (phrase, op_type, pattern, alphabet)"""
        if prefer_safe:
            # Prefer operations that work well in composites
            op = random.choice(["STARTS_WITH", "ENDS_WITH", "CONTAINS", "EXACT_LENGTH"])
        else:
            op = random.choice(["STARTS_WITH", "ENDS_WITH", "CONTAINS", "EXACT_LENGTH", "DIVISIBLE_BY"])

        if op in ["STARTS_WITH", "ENDS_WITH", "CONTAINS"]:
            # Sometimes use context header
            if random.random() < 0.2:
                context_header, char_set = get_context_header()
                pattern = get_random_pattern(char_set, random.randint(1, 3))
                phrase = context_header + get_random_phrasing(op, pattern)
                return phrase, op, pattern, char_set
            else:
                char_set = random.choice([BINARY_CHARS, LETTER_CHARS[:2]])
                pattern = get_random_pattern(char_set, random.randint(1, 3))
                return get_random_phrasing(op, pattern), op, pattern, char_set
        elif op == "EXACT_LENGTH":
            n = random.randint(2, 6)  # Slightly larger to accommodate patterns
            # Sometimes use context header
            if random.random() < 0.2:
                context_header, alphabet = get_context_header()
                return context_header + f"length is {n}", op, str(n), alphabet
            else:
                return f"length is {n}", op, str(n), BINARY_CHARS
        else:
            n = random.randint(2, 5)
            # Sometimes use context header
            if random.random() < 0.2:
                context_header, alphabet = get_context_header()
                return context_header + f"divisible by {n}", op, str(n), alphabet
            else:
                return f"divisible by {n}", op, str(n), BINARY_CHARS

    for _ in range(count):
        # Decide logic type
        logic = random.choice(["and", "or"])

        # For AND, try to use safe combinations more often
        prefer_safe = (logic == "and" and random.random() < 0.7)

        part1_phrase, op1, pat1, alpha1 = get_random_atomic_for_composite(prefer_safe)
        part2_phrase, op2, pat2, alpha2 = get_random_atomic_for_composite(prefer_safe)

        prompt = f"{part1_phrase} {logic} {part2_phrase}"

        # Determine if it's an alphabet clash
        is_clash = set(alpha1) != set(alpha2)

        # Detect if this is a logical contradiction
        is_contradiction = detect_contradiction(prompt)

        # Use the CompositeOracleSolver for proper oracle generation
        if is_clash:
            # Alphabet clash - can't easily generate valid oracles
            must_accept = []
            must_reject = []
        else:
            # Use the solver for proper composite oracle generation
            must_accept, must_reject = CompositeOracleSolver.solve_composite(
                logic=logic,
                op1=op1, pat1=pat1, alpha1=alpha1,
                op2=op2, pat2=pat2, alpha2=alpha2,
                is_contradiction=is_contradiction
            )

        # Determine category
        if is_clash:
            category = "Composite_Clash"
        elif is_contradiction:
            category = "Composite_Contradiction"
        else:
            category = f"Composite_{logic.upper()}"

        # FIX: Discard "Phantom Tests" - tests with no oracle data
        # Unless it's a contradiction (which has empty language by definition)
        if not must_accept and not must_reject and not is_contradiction:
            # Skip this test - it would pass by default (Phantom Pass)
            continue

        tests.append({
            "prompt": prompt,
            "category": category,
            "expected_type": logic.upper(),
            "difficulty": "hard",
            "must_accept": ";".join(must_accept),
            "must_reject": ";".join(must_reject),
            "is_contradiction": "true" if is_contradiction else "false"
        })
    return tests

# =============================================================================
# MAIN GENERATOR
# =============================================================================

def generate_test_suite(target_count: int) -> List[Dict[str, Any]]:
    print(f"[*] Generating {target_count} total tests...")
    
    # Approximate distribution
    atomic_count = int(target_count * 0.4)
    numeric_count = int(target_count * 0.15)
    parity_count = int(target_count * 0.15)
    composite_count = target_count - atomic_count - numeric_count - parity_count
    
    all_tests = []
    all_tests.extend(generate_atomic_pattern_tests(atomic_count))
    all_tests.extend(generate_numeric_tests(numeric_count))
    all_tests.extend(generate_parity_tests(parity_count))
    all_tests.extend(generate_composite_tests(composite_count))
    
    # Deduplicate
    seen = set()
    unique = []
    for test in all_tests:
        key = test["prompt"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(test)
            
    print(f"[+] Unique tests generated: {len(unique)}")
    
    # If we need more due to collisions, recurse with more
    if len(unique) < target_count:
        print(f"[*] Collision detected, generating {target_count - len(unique)} more...")
        more = generate_test_suite(target_count - len(unique))
        unique.extend(more)
        
    return unique[:target_count]

def export_to_csv(tests: List[Dict[str, Any]], filepath: str) -> None:
    fieldnames = ["prompt", "category", "expected_type", "difficulty", "must_accept", "must_reject", "is_contradiction"]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(tests)
    print(f"[+] Exported {len(tests)} tests to: {filepath}")

def main():
    parser = argparse.ArgumentParser(description="Generate large-scale DFA test suite with Oracle Logic")
    parser.add_argument("--output", "-o", type=str, default="generated_tests.csv", help="Output CSV file")
    parser.add_argument("--count", "-n", type=int, default=6000, help="Number of tests to generate")
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("  AUTO-DFA LARGE SCALE TEST GENERATOR (with Oracle Logic)")
    print(f"  Target: {args.count} tests")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print("=" * 70 + "\n")
    
    tests = generate_test_suite(args.count)
    random.shuffle(tests)
    export_to_csv(tests, args.output)
    
    # Print oracle coverage stats
    with_accept = sum(1 for t in tests if t.get("must_accept"))
    with_reject = sum(1 for t in tests if t.get("must_reject"))
    contradictions = sum(1 for t in tests if t.get("is_contradiction") == "true")
    
    print("\n" + "=" * 70)
    print(f"  TOTAL: {len(tests)} tests generated")
    print(f"  With Oracle Accept Strings: {with_accept} ({with_accept/len(tests)*100:.1f}%)")
    print(f"  With Oracle Reject Strings: {with_reject} ({with_reject/len(tests)*100:.1f}%)")
    print(f"  Detected Contradictions: {contradictions}")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
