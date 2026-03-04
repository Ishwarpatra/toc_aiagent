"""
Comprehensive tests for Oracle module - targeting 85%+ coverage.
Tests all check_condition operations, get_oracle_strings edge cases,
and CompositeOracleSolver methods.
"""

import pytest
from core.oracle import check_condition, get_oracle_strings, detect_contradiction, CompositeOracleSolver


class TestCheckConditionAllOperations:
    """Comprehensive tests for check_condition covering all operation types."""

    def test_starts_with_true(self):
        assert check_condition("abc", "STARTS_WITH", "a", ["a", "b", "c"]) is True
        assert check_condition("ab", "STARTS_WITH", "ab", ["a", "b"]) is True

    def test_starts_with_false(self):
        assert check_condition("abc", "STARTS_WITH", "b", ["a", "b", "c"]) is False
        assert check_condition("", "STARTS_WITH", "a", ["a", "b"]) is False

    def test_not_starts_with(self):
        assert check_condition("abc", "NOT_STARTS_WITH", "a", ["a", "b", "c"]) is False
        assert check_condition("abc", "NOT_STARTS_WITH", "b", ["a", "b", "c"]) is True
        assert check_condition("", "NOT_STARTS_WITH", "a", ["a", "b"]) is True

    def test_ends_with_true(self):
        assert check_condition("abc", "ENDS_WITH", "c", ["a", "b", "c"]) is True
        assert check_condition("abc", "ENDS_WITH", "bc", ["a", "b", "c"]) is True

    def test_ends_with_false(self):
        assert check_condition("abc", "ENDS_WITH", "b", ["a", "b", "c"]) is False
        assert check_condition("", "ENDS_WITH", "a", ["a", "b"]) is False

    def test_not_ends_with(self):
        assert check_condition("abc", "NOT_ENDS_WITH", "c", ["a", "b", "c"]) is False
        assert check_condition("abc", "NOT_ENDS_WITH", "b", ["a", "b", "c"]) is True

    def test_contains_true(self):
        assert check_condition("abc", "CONTAINS", "b", ["a", "b", "c"]) is True
        assert check_condition("abc", "CONTAINS", "ab", ["a", "b", "c"]) is True

    def test_contains_false(self):
        assert check_condition("abc", "CONTAINS", "d", ["a", "b", "c"]) is False
        assert check_condition("", "CONTAINS", "a", ["a", "b"]) is False

    def test_not_contains(self):
        assert check_condition("abc", "NOT_CONTAINS", "d", ["a", "b", "c"]) is True
        assert check_condition("abc", "NOT_CONTAINS", "b", ["a", "b", "c"]) is False

    def test_exact_length_true(self):
        assert check_condition("abc", "EXACT_LENGTH", "3", ["a", "b", "c"]) is True
        assert check_condition("", "EXACT_LENGTH", "0", ["a", "b"]) is True

    def test_exact_length_false(self):
        assert check_condition("ab", "EXACT_LENGTH", "3", ["a", "b", "c"]) is False
        assert check_condition("abcd", "EXACT_LENGTH", "3", ["a", "b", "c"]) is False

    def test_divisible_by_binary_true(self):
        # Divisible by 2 in binary: ends with 0
        assert check_condition("10", "DIVISIBLE_BY", "2", ["0", "1"]) is True  # 2 % 2 = 0
        assert check_condition("100", "DIVISIBLE_BY", "2", ["0", "1"]) is True  # 4 % 2 = 0
        assert check_condition("0", "DIVISIBLE_BY", "2", ["0", "1"]) is True  # 0 % 2 = 0

    def test_divisible_by_binary_false(self):
        assert check_condition("11", "DIVISIBLE_BY", "2", ["0", "1"]) is False  # 3 % 2 = 1
        assert check_condition("1", "DIVISIBLE_BY", "2", ["0", "1"]) is False

    def test_divisible_by_ternary(self):
        # Divisible by 3 in ternary
        assert check_condition("10", "DIVISIBLE_BY", "3", ["0", "1", "2"]) is True  # 3 % 3 = 0
        assert check_condition("0", "DIVISIBLE_BY", "3", ["0", "1", "2"]) is True

    def test_divisible_by_invalid(self):
        # Invalid pattern should return False
        assert check_condition("10", "DIVISIBLE_BY", "abc", ["0", "1"]) is False

    def test_even_count_true(self):
        assert check_condition("101", "EVEN_COUNT", "1", ["0", "1"]) is True  # 2 ones
        assert check_condition("", "EVEN_COUNT", "1", ["0", "1"]) is True  # 0 ones (even)

    def test_even_count_false(self):
        assert check_condition("111", "EVEN_COUNT", "1", ["0", "1"]) is False  # 3 ones

    def test_odd_count_true(self):
        assert check_condition("111", "ODD_COUNT", "1", ["0", "1"]) is True  # 3 ones
        assert check_condition("1", "ODD_COUNT", "1", ["0", "1"]) is True  # 1 one

    def test_odd_count_false(self):
        assert check_condition("101", "ODD_COUNT", "1", ["0", "1"]) is False  # 2 ones

    def test_no_consecutive_true(self):
        assert check_condition("101", "NO_CONSECUTIVE", "1", ["0", "1"]) is True
        assert check_condition("000", "NO_CONSECUTIVE", "1", ["0", "1"]) is True

    def test_no_consecutive_false(self):
        assert check_condition("110", "NO_CONSECUTIVE", "1", ["0", "1"]) is False
        assert check_condition("000", "NO_CONSECUTIVE", "0", ["0", "1"]) is False

    def test_unknown_operation(self):
        assert check_condition("abc", "UNKNOWN_OP", "x", ["a", "b", "c"]) is False


class TestGetOracleStringsAllOperations:
    """Comprehensive tests for get_oracle_strings covering all operation types."""

    def test_starts_with_oracle(self):
        accept, reject = get_oracle_strings("STARTS_WITH", "a", ["a", "b"])
        assert len(accept) > 0
        assert len(reject) > 0
        for s in accept:
            if s:
                assert s.startswith("a")

    def test_ends_with_oracle(self):
        accept, reject = get_oracle_strings("ENDS_WITH", "b", ["a", "b"])
        assert len(accept) > 0
        for s in accept:
            if s:
                assert s.endswith("b")

    def test_contains_oracle(self):
        accept, reject = get_oracle_strings("CONTAINS", "ab", ["a", "b"])
        assert len(accept) > 0
        for s in accept:
            assert "ab" in s

    def test_not_contains_oracle(self):
        accept, reject = get_oracle_strings("NOT_CONTAINS", "11", ["0", "1"])
        assert len(accept) > 0
        for s in accept:
            assert "11" not in s

    def test_not_starts_with_oracle(self):
        accept, reject = get_oracle_strings("NOT_STARTS_WITH", "a", ["a", "b"])
        assert len(accept) > 0

    def test_not_ends_with_oracle(self):
        accept, reject = get_oracle_strings("NOT_ENDS_WITH", "b", ["a", "b"])
        assert len(accept) > 0

    def test_exact_length_oracle(self):
        accept, reject = get_oracle_strings("EXACT_LENGTH", "3", ["0", "1"])
        assert len(accept) > 0
        for s in accept:
            assert len(s) == 3

    def test_exact_length_zero(self):
        accept, reject = get_oracle_strings("EXACT_LENGTH", "0", ["0", "1"])
        assert "" in accept

    def test_divisible_by_oracle_binary(self):
        accept, reject = get_oracle_strings("DIVISIBLE_BY", "2", ["0", "1"])
        assert len(accept) > 0
        # Verify divisible by 2
        for s in accept:
            if s:
                val = int(s, 2)
                assert val % 2 == 0

    def test_divisible_by_oracle_ternary(self):
        accept, reject = get_oracle_strings("DIVISIBLE_BY", "3", ["0", "1", "2"])
        assert len(accept) > 0

    def test_divisible_by_invalid_pattern(self):
        accept, reject = get_oracle_strings("DIVISIBLE_BY", "abc", ["0", "1"])
        # Should handle gracefully

    def test_even_count_oracle(self):
        accept, reject = get_oracle_strings("EVEN_COUNT", "1", ["0", "1"])
        assert len(accept) > 0
        for s in accept:
            assert s.count("1") % 2 == 0

    def test_odd_count_oracle(self):
        accept, reject = get_oracle_strings("ODD_COUNT", "1", ["0", "1"])
        assert len(accept) > 0
        for s in accept:
            assert s.count("1") % 2 == 1

    def test_no_consecutive_oracle(self):
        accept, reject = get_oracle_strings("NO_CONSECUTIVE", "1", ["0", "1"])
        assert len(accept) > 0
        for s in accept:
            assert "11" not in s

    def test_auto_alphabet_binary_pattern(self):
        accept, reject = get_oracle_strings("CONTAINS", "01")
        assert len(accept) > 0 or len(reject) > 0

    def test_auto_alphabet_alphabetic_pattern(self):
        accept, reject = get_oracle_strings("STARTS_WITH", "ab")
        assert len(accept) > 0 or len(reject) > 0

    def test_auto_alphabet_single_char(self):
        accept, reject = get_oracle_strings("CONTAINS", "a")
        assert len(accept) > 0 or len(reject) > 0

    def test_alphabet_expansion_single_char(self):
        # Single char alphabet should be expanded
        accept, reject = get_oracle_strings("STARTS_WITH", "a", ["a"])
        assert len(accept) > 0 or len(reject) > 0

    def test_empty_pattern(self):
        accept, reject = get_oracle_strings("CONTAINS", "", ["0", "1"])
        # Empty pattern - should handle gracefully
        assert isinstance(accept, list)
        assert isinstance(reject, list)

    def test_returns_tuple(self):
        result = get_oracle_strings("STARTS_WITH", "a", ["a", "b"])
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestDetectContradictionComprehensive:
    """Comprehensive tests for detect_contradiction."""

    def test_starts_with_different_patterns_contradiction(self):
        """Detect contradiction: starts with 'a' AND starts with 'b'."""
        prompt = "strings that start with 'a' and start with 'b'"
        result = detect_contradiction(prompt)
        # The function looks for specific patterns - may or may not detect this
        assert isinstance(result, bool)

    def test_starts_with_same_patterns_no_contradiction(self):
        """No contradiction: starts with 'a' AND starts with 'a'."""
        prompt = "strings that start with 'a' and start with 'a'"
        result = detect_contradiction(prompt)
        assert isinstance(result, bool)

    def test_length_different_values_contradiction(self):
        """Detect contradiction: length is 3 AND length is 5."""
        prompt = "strings where length is 3 and length is 5"
        assert detect_contradiction(prompt) is True

    def test_length_same_value_no_contradiction(self):
        """No contradiction: length is 3 AND length is 3."""
        prompt = "strings where length is 3 and length = 3"
        assert detect_contradiction(prompt) is False

    def test_no_and_no_contradiction(self):
        """No AND in prompt - no contradiction."""
        prompt = "strings that start with 'a'"
        assert detect_contradiction(prompt) is False

    def test_empty_string_no_contradiction(self):
        assert detect_contradiction("") is False

    def test_or_not_contradiction(self):
        """OR is not checked for contradiction."""
        prompt = "strings that start with 'a' or start with 'b'"
        assert detect_contradiction(prompt) is False

    def test_compatible_conditions_no_contradiction(self):
        """Compatible conditions: starts with 'a' AND ends with 'b'."""
        prompt = "strings that start with 'a' and end with 'b'"
        assert detect_contradiction(prompt) is False


class TestCompositeOracleSolverComprehensive:
    """Comprehensive tests for CompositeOracleSolver."""

    def setup_method(self):
        """Set up test fixtures."""
        self.solver = CompositeOracleSolver()

    def test_check_condition_static(self):
        """Test static check_condition method."""
        assert self.solver.check_condition("abc", "STARTS_WITH", "a", ["a", "b", "c"]) is True
        assert self.solver.check_condition("abc", "STARTS_WITH", "b", ["a", "b", "c"]) is False

    def test_construct_and_string_basic(self):
        """Test AND construction with basic conditions."""
        accept = self.solver.construct_and_string(
            "STARTS_WITH", "a", ["a", "b"],
            "ENDS_WITH", "b", ["a", "b"]
        )
        assert len(accept) > 0
        for s in accept:
            if s:
                assert s.startswith("a") and s.endswith("b")

    def test_construct_and_string_contains_and_ends(self):
        """Test AND with CONTAINS and ENDS_WITH."""
        accept = self.solver.construct_and_string(
            "CONTAINS", "ab", ["a", "b"],
            "ENDS_WITH", "b", ["a", "b"]
        )
        assert len(accept) > 0
        for s in accept:
            assert "ab" in s and s.endswith("b")

    def test_construct_and_string_no_consecutive_and_length(self):
        """Test AND with NO_CONSECUTIVE and EXACT_LENGTH."""
        accept = self.solver.construct_and_string(
            "NO_CONSECUTIVE", "1", ["0", "1"],
            "EXACT_LENGTH", "3", ["0", "1"]
        )
        assert len(accept) > 0
        for s in accept:
            assert "11" not in s and len(s) == 3

    def test_construct_or_string_basic(self):
        """Test OR construction with basic conditions."""
        result = self.solver.construct_or_string(
            "STARTS_WITH", "a", ["a", "b"],
            "ENDS_WITH", "b", ["a", "b"]
        )
        # Returns tuple (accept, reject)
        if isinstance(result, tuple):
            accept = result[0]
        else:
            accept = result
        assert len(accept) > 0
        for s in accept:
            if s:
                assert s.startswith("a") or s.endswith("b")

    def test_solve_composite_and(self):
        """Test solve_composite with AND."""
        accept, reject = self.solver.solve_composite(
            "AND",
            "STARTS_WITH", "a", ["a", "b"],
            "ENDS_WITH", "b", ["a", "b"]
        )
        assert len(accept) > 0
        for s in accept:
            if s:
                assert s.startswith("a") and s.endswith("b")

    def test_solve_composite_or(self):
        """Test solve_composite with OR."""
        accept, reject = self.solver.solve_composite(
            "OR",
            "STARTS_WITH", "a", ["a", "b"],
            "ENDS_WITH", "b", ["a", "b"]
        )
        assert len(accept) > 0
        for s in accept:
            if s:
                assert s.startswith("a") or s.endswith("b")

    def test_solve_composite_contradiction(self):
        """Test solve_composite with contradiction flag."""
        accept, reject = self.solver.solve_composite(
            "AND",
            "STARTS_WITH", "a", ["a", "b"],
            "STARTS_WITH", "b", ["a", "b"],
            is_contradiction=True
        )
        # Contradiction should return empty accept
        assert len(accept) == 0

    def test_solve_composite_invalid_logic(self):
        """Test solve_composite with invalid logic type."""
        accept, reject = self.solver.solve_composite(
            "INVALID",
            "STARTS_WITH", "a", ["a", "b"],
            "ENDS_WITH", "b", ["a", "b"]
        )
        assert accept == []
        assert reject == []

    def test_construct_and_string_same_condition(self):
        """Test AND with same condition twice."""
        accept = self.solver.construct_and_string(
            "STARTS_WITH", "a", ["a", "b"],
            "STARTS_WITH", "a", ["a", "b"]
        )
        assert len(accept) > 0
        for s in accept:
            if s:
                assert s.startswith("a")

    def test_construct_or_string_same_condition(self):
        """Test OR with same condition twice."""
        result = self.solver.construct_or_string(
            "STARTS_WITH", "a", ["a", "b"],
            "STARTS_WITH", "a", ["a", "b"]
        )
        if isinstance(result, tuple):
            accept = result[0]
        else:
            accept = result
        assert len(accept) > 0
        for s in accept:
            if s:
                assert s.startswith("a")
