import pytest
from core.validator import DeterministicValidator, LogicSpec

# Initialize the engine once
validator = DeterministicValidator()

def check(logic_type, target, input_str):
    spec = LogicSpec(logic_type=logic_type, target=target)
    # This calls the PUBLIC method now
    return validator.get_truth(input_str, spec)

# --- 1. STARTS WITH Tests ---
def test_starts_with():
    # Basic
    assert check("STARTS_WITH", "b", "b") is True
    assert check("STARTS_WITH", "b", "ba") is True
    assert check("STARTS_WITH", "b", "a") is False
    assert check("STARTS_WITH", "b", "") is False 
    
    # Substring target
    assert check("STARTS_WITH", "ab", "abc") is True
    assert check("STARTS_WITH", "ab", "ac") is False

# --- 2. ENDS WITH Tests ---
def test_ends_with():
    assert check("ENDS_WITH", "ab", "bab") is True
    assert check("ENDS_WITH", "ab", "ab") is True
    assert check("ENDS_WITH", "ab", "aba") is False
    assert check("ENDS_WITH", "a", "b") is False

# --- 3. CONTAINS Tests ---
def test_contains():
    t = "aba"
    assert check("CONTAINS", t, "aba") is True      
    assert check("CONTAINS", t, "babac") is True    
    assert check("CONTAINS", t, "ab") is False      
    assert check("CONTAINS", t, "") is False

# --- 4. NEGATION Tests ---
def test_not_starts_with():
    assert check("NOT_STARTS_WITH", "b", "a") is True
    assert check("NOT_STARTS_WITH", "b", "") is True 
    assert check("NOT_STARTS_WITH", "b", "b") is False

def test_not_contains():
    assert check("NOT_CONTAINS", "aa", "aba") is True
    assert check("NOT_CONTAINS", "aa", "baab") is False

# --- 5. EDGE CASE: Empty Target ---
def test_empty_target_behavior():
    assert check("STARTS_WITH", "", "abc") is True
    assert check("CONTAINS", "", "abc") is True
import pytest
from core.validator import DeterministicValidator, LogicSpec

validator = DeterministicValidator()

def check(logic_type, target, input_str, alphabet=None):
    spec = LogicSpec(logic_type=logic_type, target=target, alphabet=alphabet or ["0","1"])
    return validator.get_truth(input_str, spec)

# Pattern tests
def test_starts_with_multi():
    assert check("STARTS_WITH", "101", "1010", alphabet=["0","1"]) is True
    assert check("STARTS_WITH", "101", "1101", alphabet=["0","1"]) is False

def test_ends_with_contains():
    assert check("CONTAINS", "110", "01101", alphabet=["0","1"]) is True
    assert check("CONTAINS", "110", "01010", alphabet=["0","1"]) is False
    assert check("ENDS_WITH", "01", "1101", alphabet=["0","1"]) is True
    assert check("ENDS_WITH", "01", "11010", alphabet=["0","1"]) is False

def test_not_contains():
    assert check("NOT_CONTAINS", "00", "10101", alphabet=["0","1"]) is True
    assert check("NOT_CONTAINS", "00", "1001", alphabet=["0","1"]) is False

# Length tests
def test_exact_length():
    assert check("EXACT_LENGTH", "3", "101", alphabet=["0","1"]) is True
    assert check("EXACT_LENGTH", "3", "1010", alphabet=["0","1"]) is False

def test_min_max_length():
    assert check("MIN_LENGTH", "2", "101", alphabet=["0","1"]) is True
    assert check("MAX_LENGTH", "2", "101", alphabet=["0","1"]) is False

def test_length_mod():
    assert check("LENGTH_MOD", "1:2", "101", alphabet=["0","1"]) is True
    assert check("LENGTH_MOD", "0:2", "101", alphabet=["0","1"]) is False

def test_count_mod_and_even_odd_counts():
    assert check("COUNT_MOD", "1:1:2", "101", alphabet=["0","1"]) is True
    assert check("EVEN_COUNT", "1", "11", alphabet=["0","1"]) is True
    assert check("ODD_COUNT", "1", "101", alphabet=["0","1"]) is True

# Divisibility tests
def test_divisible_by_3_binary():
    assert check("DIVISIBLE_BY", "3", "11", alphabet=["0","1"]) is True
    assert check("DIVISIBLE_BY", "3", "10", alphabet=["0","1"]) is False

def test_even_number_divisible_by_2():
    assert check("EVEN_NUMBER", None, "10", alphabet=["0","1"]) is True
    assert check("EVEN_NUMBER", None, "11", alphabet=["0","1"]) is False

# Product parity
def test_product_even_binary():
    assert check("PRODUCT_EVEN", None, "1010", alphabet=["0","1"]) is True
    assert check("PRODUCT_EVEN", None, "1111", alphabet=["0","1"]) is False