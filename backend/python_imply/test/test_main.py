"""
Tests for main.DFAGeneratorSystem pipeline.
"""
import pytest
from main import DFAGeneratorSystem, DFA
from core.validator import DeterministicValidator, LogicSpec

# Initialize the engine once per test session
@pytest.fixture(scope="module")
def dfa_system():
    return DFAGeneratorSystem(model_name="test")

@pytest.fixture(scope="module")
def det_validator():
    return DeterministicValidator()

# --- Agent Prompt Parsing Tests ---
def test_analyst_ends_with(dfa_system):
    spec = dfa_system.analyst.analyze("Design a DFA that accepts strings ending with 'b'")
    assert spec.logic_type == "ENDS_WITH"
    assert spec.target == "b"

def test_analyst_starts_with(dfa_system):
    spec = dfa_system.analyst.analyze("Design a DFA that accepts strings starting with 'a'")
    assert spec.logic_type == "STARTS_WITH"
    assert spec.target == "a"

def test_analyst_contains(dfa_system):
    spec = dfa_system.analyst.analyze("Design a DFA that accepts strings containing '01'")
    assert spec.logic_type == "CONTAINS"
    assert spec.target == "01"

def test_architect_design(dfa_system):
    spec = dfa_system.analyst.analyze("strings ending with 'b'")
    dfa = dfa_system.architect.design(spec)
    assert isinstance(dfa, DFA)
    assert dfa.start_state is not None
    assert dfa.accept_states is not None
    assert len(dfa.accept_states) > 0
    assert dfa.alphabet is not None

def check(validator, logic_type, target, input_str):
    spec = LogicSpec(logic_type=logic_type, target=target)
    return validator.get_truth(input_str, spec)

# --- Validator Tests ---
def test_validator_starts_with(det_validator):
    assert check(det_validator, "STARTS_WITH", "b", "b") is True
    assert check(det_validator, "STARTS_WITH", "b", "ba") is True
    assert check(det_validator, "STARTS_WITH", "b", "a") is False

def test_validator_ends_with(det_validator):
    assert check(det_validator, "ENDS_WITH", "b", "ab") is True
    assert check(det_validator, "ENDS_WITH", "b", "a") is False

def test_validator_contains(det_validator):
    assert check(det_validator, "CONTAINS", "01", "001") is True
    assert check(det_validator, "CONTAINS", "01", "00") is False

def test_full_pipeline(dfa_system, det_validator):
    """Test the full Analyst -> Architect -> Validator pipeline."""
    prompt = "strings starting with 'a'"
    
    # Analyst
    spec = dfa_system.analyst.analyze(prompt)
    assert spec.logic_type == "STARTS_WITH"
    
    # Architect
    dfa = dfa_system.architect.design(spec)
    assert isinstance(dfa, DFA)
    
    # Validator
    is_valid, error_msg = dfa_system.validator.validate(dfa, spec)
    assert is_valid is True or error_msg is None
