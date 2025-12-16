import pytest
from validator import DeterministicValidator, LogicSpec

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