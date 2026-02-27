"""
Oracle Module for Auto-DFA
Contains the CompositeOracleSolver and related validation logic.
Separated from test generation to enable reuse in production.
"""

import random
import itertools
from typing import List, Tuple, Dict, Any
import string


def check_condition(s: str, op_type: str, pattern: str, alphabet: List[str]) -> bool:
    """Authority on whether a string satisfies a given condition."""
    if op_type == "STARTS_WITH":
        return s.startswith(pattern)
    elif op_type == "NOT_STARTS_WITH":
        return not s.startswith(pattern)
    elif op_type == "ENDS_WITH":
        return s.endswith(pattern)
    elif op_type == "NOT_ENDS_WITH":
        return not s.endswith(pattern)
    elif op_type == "CONTAINS":
        return pattern in s
    elif op_type == "NOT_CONTAINS":
        return pattern not in s
    elif op_type == "EXACT_LENGTH":
        try:
            return len(s) == int(pattern)
        except:
            return False
    elif op_type == "DIVISIBLE_BY":
        try:
            n = int(pattern)
            if set(alphabet) == set(['0', '1']):
                val = int(s, 2) if s else 0
            else:
                # For base-agnostic divisibility, map symbols to digits
                mapping = {sym: idx for idx, sym in enumerate(alphabet)}
                val = 0
                for char in s:
                    digit = mapping.get(char, 0)
                    val = val * len(alphabet) + digit
            return val % n == 0
        except:
            return False
    elif op_type == "EVEN_COUNT":
        return s.count(pattern) % 2 == 0
    elif op_type == "ODD_COUNT":
        return s.count(pattern) % 2 == 1
    elif op_type == "NO_CONSECUTIVE":
        return (pattern * 2) not in s
    return False


def get_oracle_strings(op_type: str, pattern: str, alphabet: List[str] = None) -> Tuple[List[str], List[str]]:
    """
    Generate authoritative oracle strings for a given operation.
    Uses constructive generation followed by randomized verification to guarantee truth.
    """
    if alphabet is None:
        if all(c in ['0', '1'] for c in pattern):
            alphabet = ['0', '1']
        elif all(c in list(string.ascii_lowercase[:6]) for c in pattern):
            alphabet = ['a', 'b']
        else:
            alphabet = sorted(set(pattern)) if pattern else ['0', '1']

    if len(alphabet) < 2:
        alphabet = sorted(set(alphabet) | {'0', '1'})[:2]

    accept = []
    reject = []

    # 1. Constructive candidates
    candidates = ["", pattern]
    if len(pattern) >= 1:
        candidates.extend([
            pattern + alphabet[0],
            alphabet[0] + pattern,
            pattern + alphabet[1],
            alphabet[1] + pattern,
            pattern[:-1],
            pattern + pattern,
            alphabet[0] * (len(pattern) + 1),
            alphabet[1] * (len(pattern) + 1)
        ])

    if op_type == "DIVISIBLE_BY":
        try:
            n = int(pattern)
            for i in range(1, 10):
                # Generate numbers divisible by n in the given base
                if len(alphabet) == 2 and set(alphabet) == set(['0', '1']):
                    # Binary case
                    candidates.append(bin(i * n)[2:])
                    candidates.append(bin(i * n + 1)[2:])
                else:
                    # For other bases, convert to the appropriate representation
                    val = i * n
                    if val == 0:
                        candidates.append(alphabet[0])  # 0 in any base
                    else:
                        # Convert number to the given base/alphabet
                        num_str = ""
                        temp_val = val
                        while temp_val > 0:
                            num_str = alphabet[temp_val % len(alphabet)] + num_str
                            temp_val //= len(alphabet)
                        if num_str:
                            candidates.append(num_str)
        except: pass
    elif op_type == "EXACT_LENGTH":
        try:
            n = int(pattern)
            candidates.append(alphabet[0] * n)
            candidates.append(alphabet[0] * (n-1) if n > 0 else alphabet[0])
            candidates.append(alphabet[0] * (n+1))
        except: pass

    # 2. Random sampling
    for _ in range(40):
        rand_len = random.randint(0, 15)
        candidates.append("".join(random.choice(alphabet) for _ in range(rand_len)))

    # 3. Precise categorization
    for s in list(dict.fromkeys(candidates)):
        if check_condition(s, op_type, pattern, alphabet):
            accept.append(s)
        else:
            reject.append(s)

    random.shuffle(accept)
    random.shuffle(reject)
    return accept[:5], reject[:5]


def detect_contradiction(prompt: str) -> bool:
    """
    Detect if a composite prompt contains logical contradictions.

    Returns True if the prompt is logically impossible (Empty Language case).
    """
    prompt_lower = prompt.lower()

    # Check for AND with incompatible conditions
    if " and " in prompt_lower:
        parts = prompt_lower.split(" and ")

        # Check for "starts with X AND starts with Y" where X != Y
        starts_patterns = []
        for part in parts:
            if "starts with" in part:
                # Extract pattern between quotes
                import re
                match = re.search(r"['\"]([^'\"]+)['\"]", part)
                if match:
                    starts_patterns.append(match.group(1))

        if len(starts_patterns) >= 2:
            # Check if patterns are incompatible
            for i, p1 in enumerate(starts_patterns):
                for p2 in starts_patterns[i+1:]:
                    min_len = min(len(p1), len(p2))
                    if p1[:min_len] != p2[:min_len]:
                        return True  # Contradiction!

        # Check for "length is X AND length is Y" where X != Y
        length_vals = []
        for part in parts:
            if "length is" in part or "length =" in part:
                import re
                match = re.search(r"length\s*(?:is|=)\s*(\d+)", part)
                if match:
                    length_vals.append(int(match.group(1)))

        if len(set(length_vals)) > 1:
            return True  # Different length requirements = contradiction

    return False


class CompositeOracleSolver:
    """
    Constructive solver for generating oracle strings for composite (AND/OR) operations.

    The key insight is that we cannot just grab strings from individual operation pools.
    For AND: we need strings that satisfy BOTH conditions simultaneously.
    For OR: strings from either pool work, but we should prefer diverse examples.

    This solver uses constructive generation to mathematically guarantee correctness.
    """

    @staticmethod
    def check_condition(s: str, op_type: str, pattern: str, alphabet: List[str]) -> bool:
        """Check if a string satisfies a given condition."""
        return check_condition(s, op_type, pattern, alphabet)

    @staticmethod
    def construct_and_string(
        op1: str, pat1: str, alpha1: List[str],
        op2: str, pat2: str, alpha2: List[str]
    ) -> List[str]:
        """
        Construct strings that satisfy BOTH conditions (AND).

        Strategy: Start with candidates that satisfy the harder condition,
        then filter to those that also satisfy the easier condition.
        """
        results = []

        # Merge alphabets
        alphabet = sorted(set(alpha1) | set(alpha2))
        if not alphabet:
            alphabet = ['0', '1']

        # Strategy 1: For STARTS_WITH AND ENDS_WITH - construct directly
        if op1 == "STARTS_WITH" and op2 == "ENDS_WITH":
            # Build: prefix + padding + suffix
            min_len = len(pat1) + len(pat2)
            # Check for overlap
            if pat1.endswith(pat2[:min(len(pat1), len(pat2))]):
                # Patterns can overlap
                results.append(pat1 + pat2[len(pat1):] if len(pat1) < len(pat2) else pat1)
            else:
                # Need separation
                results.append(pat1 + pat2)
                if len(alphabet) > 0:
                    results.append(pat1 + alphabet[0] + pat2)

        elif op1 == "ENDS_WITH" and op2 == "STARTS_WITH":
            return CompositeOracleSolver.construct_and_string(op2, pat2, alpha2, op1, pat1, alpha1)

        # Strategy 2: For STARTS_WITH AND CONTAINS
        elif op1 == "STARTS_WITH" and op2 == "CONTAINS":
            if pat2 in pat1:
                results.append(pat1)  # Pattern already contains the substring
            else:
                results.append(pat1 + pat2)  # Append the required substring

        elif op1 == "CONTAINS" and op2 == "STARTS_WITH":
            return CompositeOracleSolver.construct_and_string(op2, pat2, alpha2, op1, pat1, alpha1)

        # Strategy 3: For STARTS_WITH AND EXACT_LENGTH
        elif op1 == "STARTS_WITH" and op2 == "EXACT_LENGTH":
            try:
                n = int(pat2)
                if n >= len(pat1):
                    # Pad the prefix to exact length
                    padding = alphabet[0] * (n - len(pat1))
                    results.append(pat1 + padding)
            except:
                pass

        elif op1 == "EXACT_LENGTH" and op2 == "STARTS_WITH":
            return CompositeOracleSolver.construct_and_string(op2, pat2, alpha2, op1, pat1, alpha1)

        # Strategy 4: For ENDS_WITH AND EXACT_LENGTH
        elif op1 == "ENDS_WITH" and op2 == "EXACT_LENGTH":
            try:
                n = int(pat2)
                if n >= len(pat1):
                    padding = alphabet[0] * (n - len(pat1))
                    results.append(padding + pat1)
            except:
                pass

        elif op1 == "EXACT_LENGTH" and op2 == "ENDS_WITH":
            return CompositeOracleSolver.construct_and_string(op2, pat2, alpha2, op1, pat1, alpha1)

        # Strategy 5: For CONTAINS AND EXACT_LENGTH
        elif op1 == "CONTAINS" and op2 == "EXACT_LENGTH":
            try:
                n = int(pat2)
                if n >= len(pat1):
                    padding = alphabet[0] * (n - len(pat1))
                    # Place pattern in the middle
                    results.append(padding[:len(padding)//2] + pat1 + padding[len(padding)//2:])
            except:
                pass

        elif op1 == "EXACT_LENGTH" and op2 == "CONTAINS":
            return CompositeOracleSolver.construct_and_string(op2, pat2, alpha2, op1, pat1, alpha1)

        # Strategy 6: Brute force for simple cases
        # Generate candidate strings and filter
        if not results:
            candidates = CompositeOracleSolver._generate_candidates(alphabet, max_len=10)
            for s in candidates:
                if (CompositeOracleSolver.check_condition(s, op1, pat1, alpha1) and
                    CompositeOracleSolver.check_condition(s, op2, pat2, alpha2)):
                    results.append(s)
                    if len(results) >= 3:
                        break

        return results[:4]

    @staticmethod
    def construct_or_string(
        op1: str, pat1: str, alpha1: List[str],
        op2: str, pat2: str, alpha2: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Construct strings for OR operations.

        For accept: strings from either condition work.
        For reject: need strings that fail BOTH conditions.
        """
        accept = []
        reject = []

        # Get individual accept strings
        accept1, reject1 = get_oracle_strings(op1, pat1, alpha1)
        accept2, reject2 = get_oracle_strings(op2, pat2, alpha2)

        # For OR, any accept from either side works
        accept = accept1[:2] + accept2[:2]

        # For reject, need to fail both - find intersection of rejects
        alphabet = sorted(set(alpha1) | set(alpha2))
        if not alphabet:
            alphabet = ['0', '1']

        # Generate candidates and find ones that fail both
        candidates = CompositeOracleSolver._generate_candidates(alphabet, max_len=8)
        for s in candidates:
            if (not CompositeOracleSolver.check_condition(s, op1, pat1, alpha1) and
                not CompositeOracleSolver.check_condition(s, op2, pat2, alpha2)):
                reject.append(s)
                if len(reject) >= 3:
                    break

        return accept[:4], reject[:3]

    @staticmethod
    def _generate_candidates(alphabet: List[str], max_len: int = 8) -> List[str]:
        """Generate candidate strings for brute-force checking."""
        candidates = [""]
        for length in range(1, max_len + 1):
            if length <= 3:
                # Full enumeration for short strings
                for combo in itertools.product(alphabet, repeat=length):
                    candidates.append("".join(combo))
            else:
                # Sample for longer strings
                for _ in range(20):
                    s = "".join(random.choice(alphabet) for _ in range(length))
                    candidates.append(s)
        return candidates

    @staticmethod
    def solve_composite(
        logic: str,
        op1: str, pat1: str, alpha1: List[str],
        op2: str, pat2: str, alpha2: List[str],
        is_contradiction: bool = False
    ) -> Tuple[List[str], List[str]]:
        """
        Main entry point for composite oracle solving.

        Returns (must_accept, must_reject) lists.
        """
        if is_contradiction:
            # Empty language - nothing should be accepted
            return [], []

        if logic.lower() == "and":
            accept = CompositeOracleSolver.construct_and_string(
                op1, pat1, alpha1, op2, pat2, alpha2
            )
            # For AND reject, need to fail at least one condition
            reject1, _ = get_oracle_strings(op1, pat1, alpha1)
            _, reject2 = get_oracle_strings(op2, pat2, alpha2)
            # Use reject strings from either side (they fail at least one)
            reject = reject2[:2] if reject2 else reject1[:2]
            return accept, reject

        elif logic.lower() == "or":
            return CompositeOracleSolver.construct_or_string(
                op1, pat1, alpha1, op2, pat2, alpha2
            )

        return [], []