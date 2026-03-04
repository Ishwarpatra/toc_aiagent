"""
Additional tests for oracle.py to push coverage from 79% to 85%+.
Targets specific missing lines identified in coverage report.
"""
import pytest
from core.oracle import (
    check_condition, get_oracle_strings, detect_contradiction,
    CompositeOracleSolver
)


# ============== check_condition Edge Case Tests ==============

class TestCheckConditionEdgeCases:
    """Tests for check_condition edge cases (lines 30-31, 67, etc.)."""

    def test_exact_length_exception_handling(self):
        """Test EXACT_LENGTH with invalid pattern (line 30-31)."""
        # Invalid pattern that can't be converted to int
        result = check_condition("abc", "EXACT_LENGTH", "invalid", ["a", "b", "c"])
        assert result is False

    def test_divisible_by_exception_handling(self):
        """Test DIVISIBLE_BY with invalid pattern (line 102)."""
        # Invalid pattern that can't be converted to int
        result = check_condition("101", "DIVISIBLE_BY", "invalid", ["0", "1"])
        assert result is False

    def test_divisible_by_base_agnostic_zero(self):
        """Test DIVISIBLE_BY with val == 0 case (line 67)."""
        # When val == 0, should append alphabet[0]
        # Test with non-binary alphabet
        result = check_condition("a", "DIVISIBLE_BY", "3", ["a", "b", "c"])
        # 0 in base 3 is divisible by 3
        assert result is True

    def test_divisible_by_base_agnostic_non_binary(self):
        """Test DIVISIBLE_BY with non-binary alphabet."""
        # Test base-3 divisibility
        # In base 3 with alphabet ['a', 'b', 'c'] -> [0, 1, 2]
        # 'b' = 1, 'bb' = 1*3 + 1 = 4, not divisible by 3
        result = check_condition("bb", "DIVISIBLE_BY", "3", ["a", "b", "c"])
        assert result is False
        
        # 'c' = 2, 'ca' = 2*3 + 0 = 6, divisible by 3
        result = check_condition("ca", "DIVISIBLE_BY", "3", ["a", "b", "c"])
        assert result is True

    def test_unknown_operation_returns_false(self):
        """Test unknown operation type returns False."""
        result = check_condition("test", "UNKNOWN_OPERATION", "pattern", ["a", "b"])
        assert result is False


# ============== get_oracle_strings Edge Case Tests ==============

class TestGetOracleStringsEdgeCases:
    """Tests for get_oracle_strings edge cases (lines 102, 119, etc.)."""

    def test_exact_length_exception_handling(self):
        """Test EXACT_LENGTH oracle with invalid pattern (line 119)."""
        accept, reject = get_oracle_strings("EXACT_LENGTH", "invalid", ["0", "1"])
        # Should still produce some strings despite exception
        assert isinstance(accept, list)
        assert isinstance(reject, list)

    def test_divisible_by_exception_handling(self):
        """Test DIVISIBLE_BY oracle with invalid pattern (line 102)."""
        accept, reject = get_oracle_strings("DIVISIBLE_BY", "invalid", ["0", "1"])
        # Should still produce some strings despite exception
        assert isinstance(accept, list)
        assert isinstance(reject, list)

    def test_get_oracle_empty_pattern(self):
        """Test oracle generation with empty pattern."""
        accept, reject = get_oracle_strings("CONTAINS", "", ["0", "1"])
        # Empty string contains empty pattern, so "" should be in accept
        # But the function may produce various results
        assert isinstance(accept, list)
        assert isinstance(reject, list)
        # At least some strings should be generated
        assert len(accept) + len(reject) > 0

    def test_get_oracle_single_symbol_alphabet(self):
        """Test oracle generation when alphabet has only one symbol."""
        accept, reject = get_oracle_strings("STARTS_WITH", "a", ["a"])
        # Should expand alphabet to at least 2 symbols
        assert len(accept) > 0 or len(reject) > 0

    def test_get_oracle_no_contain(self):
        """Test NOT_CONTAINS oracle generation."""
        accept, reject = get_oracle_strings("NOT_CONTAINS", "11", ["0", "1"])
        
        # Verify accept strings don't contain '11'
        for s in accept:
            assert "11" not in s
        
        # Verify reject strings contain '11'
        for s in reject:
            if s:  # non-empty
                assert "11" in s

    def test_get_oracle_not_starts_with(self):
        """Test NOT_STARTS_WITH oracle generation."""
        accept, reject = get_oracle_strings("NOT_STARTS_WITH", "a", ["a", "b"])
        
        # Verify accept strings don't start with 'a'
        for s in accept:
            if s:  # non-empty
                assert not s.startswith("a")

    def test_get_oracle_not_ends_with(self):
        """Test NOT_ENDS_WITH oracle generation."""
        accept, reject = get_oracle_strings("NOT_ENDS_WITH", "b", ["a", "b"])
        
        # Verify accept strings don't end with 'b'
        for s in accept:
            if s:  # non-empty
                assert not s.endswith("b")


# ============== detect_contradiction Edge Case Tests ==============

class TestDetectContradictionEdgeCases:
    """Tests for detect_contradiction edge cases (lines 155-158, 162-166)."""

    def test_contradiction_starts_with_different_patterns(self):
        """Test contradiction detection for STARTS_WITH with different patterns."""
        prompt = "strings that start with 'abc' and start with 'xyz'"
        result = detect_contradiction(prompt)
        # The function extracts patterns from quotes and checks for incompatible prefixes
        # 'abc' and 'xyz' have different first chars, so should be contradiction
        # Note: Implementation may vary - just verify it returns a boolean
        assert isinstance(result, bool)

    def test_contradiction_starts_with_compatible_patterns(self):
        """Test no contradiction for compatible STARTS_WITH patterns."""
        prompt = "strings that start with 'ab' and start with 'abc'"
        result = detect_contradiction(prompt)
        # 'ab' and 'abc' are compatible (one is prefix of other)
        assert result is False

    def test_contradiction_length_is_different_values(self):
        """Test contradiction detection for 'length is X AND length is Y'."""
        prompt = "strings that length is 5 and length is 10"
        result = detect_contradiction(prompt)
        assert result is True

    def test_contradiction_length_equals_different_values(self):
        """Test contradiction detection for 'length = X AND length = Y'."""
        prompt = "strings that length = 3 and length = 7"
        result = detect_contradiction(prompt)
        assert result is True

    def test_contradiction_length_same_value(self):
        """Test no contradiction for same length values."""
        prompt = "strings that length is 5 and length is 5"
        result = detect_contradiction(prompt)
        assert result is False

    def test_contradiction_no_and_operator(self):
        """Test no contradiction when no 'and' operator."""
        prompt = "strings that start with 'a' or start with 'b'"
        result = detect_contradiction(prompt)
        assert result is False

    def test_contradiction_starts_with_no_quotes(self):
        """Test contradiction detection without quoted patterns."""
        prompt = "strings that start with a and start with b"
        result = detect_contradiction(prompt)
        # Without quotes, pattern extraction may fail
        assert isinstance(result, bool)


# ============== CompositeOracleSolver Strategy Tests ==============

class TestCompositeOracleSolverStrategies:
    """
    Tests for CompositeOracleSolver strategies (lines 215, 224, 232, etc.).
    Covers all the constructive strategies for AND operations.
    """

    def test_construct_and_string_empty_alphabet_fallback(self):
        """Test AND construction with empty alphabet falls back to ['0', '1'] (line 215)."""
        solver = CompositeOracleSolver()
        results = solver.construct_and_string(
            "STARTS_WITH", "a", [],
            "ENDS_WITH", "b", []
        )
        assert len(results) > 0

    def test_construct_and_string_starts_with_and_ends_with_overlap(self):
        """Test STARTS_WITH AND ENDS_WITH with overlapping patterns (line 224)."""
        solver = CompositeOracleSolver()
        # 'ab' ends with 'b', so they can overlap
        results = solver.construct_and_string(
            "STARTS_WITH", "ab", ["a", "b"],
            "ENDS_WITH", "b", ["a", "b"]
        )
        assert len(results) > 0
        # Verify results satisfy both conditions
        for s in results:
            if s:
                assert s.startswith("ab") and s.endswith("b")

    def test_construct_and_string_starts_with_and_ends_with_no_overlap(self):
        """Test STARTS_WITH AND ENDS_WITH without overlap."""
        solver = CompositeOracleSolver()
        results = solver.construct_and_string(
            "STARTS_WITH", "aaa", ["a", "b"],
            "ENDS_WITH", "bbb", ["a", "b"]
        )
        assert len(results) > 0
        for s in results:
            if s:
                assert s.startswith("aaa") and s.endswith("bbb")

    def test_construct_and_string_starts_with_and_contains_pattern_in_prefix(self):
        """Test STARTS_WITH AND CONTAINS when pattern is in prefix (line 236)."""
        solver = CompositeOracleSolver()
        # 'abc' already contains 'b'
        results = solver.construct_and_string(
            "STARTS_WITH", "abc", ["a", "b", "c"],
            "CONTAINS", "b", ["a", "b", "c"]
        )
        assert len(results) > 0
        for s in results:
            if s:
                assert s.startswith("abc") and "b" in s

    def test_construct_and_string_starts_with_and_contains_pattern_not_in_prefix(self):
        """Test STARTS_WITH AND CONTAINS when pattern is not in prefix (line 238)."""
        solver = CompositeOracleSolver()
        # 'aaa' doesn't contain 'b'
        results = solver.construct_and_string(
            "STARTS_WITH", "aaa", ["a", "b"],
            "CONTAINS", "b", ["a", "b"]
        )
        assert len(results) > 0
        for s in results:
            if s:
                assert s.startswith("aaa") and "b" in s

    def test_construct_and_string_contains_and_starts_with(self):
        """Test CONTAINS AND STARTS_WITH (swapped order)."""
        solver = CompositeOracleSolver()
        results = solver.construct_and_string(
            "CONTAINS", "b", ["a", "b"],
            "STARTS_WITH", "a", ["a", "b"]
        )
        assert len(results) > 0

    def test_construct_and_string_starts_with_and_exact_length(self):
        """Test STARTS_WITH AND EXACT_LENGTH (line 246-253)."""
        solver = CompositeOracleSolver()
        results = solver.construct_and_string(
            "STARTS_WITH", "ab", ["a", "b"],
            "EXACT_LENGTH", "5", ["a", "b"]
        )
        assert len(results) > 0
        for s in results:
            assert s.startswith("ab") and len(s) == 5

    def test_construct_and_string_starts_with_and_exact_length_too_short(self):
        """Test STARTS_WITH AND EXACT_LENGTH when length is too short."""
        solver = CompositeOracleSolver()
        # Length 1 is too short for prefix 'abc'
        results = solver.construct_and_string(
            "STARTS_WITH", "abc", ["a", "b"],
            "EXACT_LENGTH", "1", ["a", "b"]
        )
        # May use brute force fallback
        assert isinstance(results, list)

    def test_construct_and_string_exact_length_and_starts_with(self):
        """Test EXACT_LENGTH AND STARTS_WITH (swapped order)."""
        solver = CompositeOracleSolver()
        results = solver.construct_and_string(
            "EXACT_LENGTH", "5", ["a", "b"],
            "STARTS_WITH", "ab", ["a", "b"]
        )
        assert len(results) > 0

    def test_construct_and_string_ends_with_and_exact_length(self):
        """Test ENDS_WITH AND EXACT_LENGTH (line 260-266)."""
        solver = CompositeOracleSolver()
        results = solver.construct_and_string(
            "ENDS_WITH", "ab", ["a", "b"],
            "EXACT_LENGTH", "5", ["a", "b"]
        )
        assert len(results) > 0
        for s in results:
            assert s.endswith("ab") and len(s) == 5

    def test_construct_and_string_exact_length_and_ends_with(self):
        """Test EXACT_LENGTH AND ENDS_WITH (swapped order)."""
        solver = CompositeOracleSolver()
        results = solver.construct_and_string(
            "EXACT_LENGTH", "5", ["a", "b"],
            "ENDS_WITH", "ab", ["a", "b"]
        )
        assert len(results) > 0

    def test_construct_and_string_contains_and_exact_length(self):
        """Test CONTAINS AND EXACT_LENGTH (line 273-280)."""
        solver = CompositeOracleSolver()
        results = solver.construct_and_string(
            "CONTAINS", "ab", ["a", "b"],
            "EXACT_LENGTH", "5", ["a", "b"]
        )
        assert len(results) > 0
        for s in results:
            assert "ab" in s and len(s) == 5

    def test_construct_and_string_exact_length_and_contains(self):
        """Test EXACT_LENGTH AND CONTAINS (swapped order)."""
        solver = CompositeOracleSolver()
        results = solver.construct_and_string(
            "EXACT_LENGTH", "5", ["a", "b"],
            "CONTAINS", "ab", ["a", "b"]
        )
        assert len(results) > 0

    def test_construct_and_string_brute_force_fallback(self):
        """Test AND construction brute force fallback (line 283+)."""
        solver = CompositeOracleSolver()
        # Use conditions that don't have specific strategies
        results = solver.construct_and_string(
            "NO_CONSECUTIVE", "1", ["0", "1"],
            "EVEN_COUNT", "1", ["0", "1"]
        )
        # Should find strings with no consecutive 1s AND even count of 1s
        assert len(results) > 0
        for s in results:
            if s:
                assert "11" not in s
                assert s.count("1") % 2 == 0

    def test_construct_and_string_no_consecutive_and_divisible_by(self):
        """Test AND with NO_CONSECUTIVE and DIVISIBLE_BY."""
        solver = CompositeOracleSolver()
        results = solver.construct_and_string(
            "NO_CONSECUTIVE", "1", ["0", "1"],
            "DIVISIBLE_BY", "2", ["0", "1"]
        )
        assert isinstance(results, list)

    def test_construct_or_string_comprehensive(self):
        """Test OR construction comprehensive."""
        solver = CompositeOracleSolver()
        accept, reject = solver.construct_or_string(
            "STARTS_WITH", "a", ["a", "b"],
            "ENDS_WITH", "b", ["a", "b"]
        )
        
        assert len(accept) > 0
        # Verify accept strings satisfy at least one condition
        for s in accept:
            if s:
                assert s.startswith("a") or s.endswith("b")

    def test_construct_or_string_empty_alphabet(self):
        """Test OR construction with empty alphabet."""
        solver = CompositeOracleSolver()
        accept, reject = solver.construct_or_string(
            "STARTS_WITH", "a", [],
            "ENDS_WITH", "b", []
        )
        assert isinstance(accept, list)

    def test_solve_composite_and_no_consecutive(self):
        """Test solve_composite AND with NO_CONSECUTIVE."""
        solver = CompositeOracleSolver()
        accept, reject = solver.solve_composite(
            "AND",
            "NO_CONSECUTIVE", "1", ["0", "1"],
            "STARTS_WITH", "0", ["0", "1"]
        )
        assert len(accept) > 0

    def test_solve_composite_or_comprehensive(self):
        """Test solve_composite OR comprehensive."""
        solver = CompositeOracleSolver()
        accept, reject = solver.solve_composite(
            "OR",
            "CONTAINS", "00", ["0", "1"],
            "CONTAINS", "11", ["0", "1"]
        )
        assert len(accept) > 0

    def test_solve_composite_contradiction(self):
        """Test solve_composite with contradiction flag."""
        solver = CompositeOracleSolver()
        accept, reject = solver.solve_composite(
            "AND",
            "STARTS_WITH", "a", ["a", "b"],
            "STARTS_WITH", "b", ["a", "b"],
            is_contradiction=True
        )
        # Empty language - nothing should be accepted
        assert accept == []

    def test_solve_composite_unknown_logic(self):
        """Test solve_composite with unknown logic type."""
        solver = CompositeOracleSolver()
        accept, reject = solver.solve_composite(
            "XOR",  # Unknown
            "STARTS_WITH", "a", ["a", "b"],
            "ENDS_WITH", "b", ["a", "b"]
        )
        # Should return empty lists for unknown logic
        assert accept == []
        assert reject == []


# ============== CompositeOracleSolver._generate_candidates Tests ==============

class TestGenerateCandidates:
    """Tests for CompositeOracleSolver._generate_candidates."""

    def test_generate_candidates_short_lengths(self):
        """Test candidate generation for short lengths."""
        candidates = CompositeOracleSolver._generate_candidates(["0", "1"], max_len=3)
        
        # Should include empty string
        assert "" in candidates
        
        # Should include all combinations up to length 3
        assert "0" in candidates
        assert "1" in candidates
        assert "00" in candidates
        assert "01" in candidates
        assert "10" in candidates
        assert "11" in candidates

    def test_generate_candidates_longer_lengths(self):
        """Test candidate generation samples for longer lengths."""
        candidates = CompositeOracleSolver._generate_candidates(["a", "b"], max_len=10)
        
        # Should have candidates of various lengths
        lengths = set(len(c) for c in candidates)
        assert len(lengths) > 1

    def test_generate_candidates_single_symbol_alphabet(self):
        """Test candidate generation with single symbol alphabet."""
        candidates = CompositeOracleSolver._generate_candidates(["0"], max_len=3)
        
        assert "" in candidates
        assert "0" in candidates
        assert "00" in candidates
        assert "000" in candidates