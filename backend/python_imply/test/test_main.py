import pytest
from main import DFAGeneratorSystem, DFA
from core.validator import DeterministicValidator, LogicSpec

# Initialize the engine once
validator = DeterministicValidator()

agents = DFAGeneratorSystem()
# "Design a DFA that accepts strings starting with 'b'"
spec = agents.agent_1_analyst("Design a DFA that accepts strings ending with 'b'")

# --- Agent Prompt Parsing Tests ---
def test_agent_1_analyst():
    assert spec.logic_type == "ENDS_WITH"
    assert spec.target == "b"

call : DFA = agents.agent_2_architect(spec)
def test_agent_2_architect():
    # assert call.states == ['q0', 'q1', 'q_dead']
    print(call.alphabet)
    print(call.start_state)
    print(call.accept_states)
    print(call.transitions)
    # assert call.alphabet == ['0', '1']
    # assert call.start_state == q0
    # assert call.accept_states == ['q1']


def check(logic_type, target, input_str):
    spec = LogicSpec(logic_type=logic_type, target=target)
    # This calls the PUBLIC method now
    return validator.get_truth(input_str, spec)

# --- 1. STARTS WITH Tests ---
if spec.logic_type == "STARTS_WITH":
    if spec.alphabet == "a":
        def test_starts_with_a():
            # Basic
            assert check("STARTS_WITH", spec.target, "b") is False
            assert check("STARTS_WITH", spec.target, "a") is True
            assert check("STARTS_WITH", spec.target, "ab") is True
            assert check("STARTS_WITH", spec.target, "ba") is False
            assert check("STARTS_WITH", spec.target, "") is False
    
    elif spec.alphabet == "b":     
        def test_starts_with_b():   
            assert check("STARTS_WITH", spec.target, "b") is True
            assert check("STARTS_WITH", spec.target, "a") is False
            assert check("STARTS_WITH", spec.target, "ab") is False
            assert check("STARTS_WITH", spec.target, "ba") is True
            assert check("STARTS_WITH", spec.target, "") is False
            
        # assert check("STARTS_WITH", "b", "b") is True
        # assert check("STARTS_WITH", "b", "ba") is True
        # assert check("STARTS_WITH", "b", "a") is False
        # assert check("STARTS_WITH", "b", "") is False 
        
#     # Substring target
#     assert check("STARTS_WITH", "ab", "abc") is True
#     assert check("STARTS_WITH", "ab", "ac") is False

# --- 2. ENDS WITH Tests ---
def test_ends_with():
    assert check("ENDS_WITH", "ab", "bab") is True
    assert check("ENDS_WITH", "ab", "ab") is True
    assert check("ENDS_WITH", "ab", "aba") is False
    assert check("ENDS_WITH", "a", "b") is False

# # --- 3. CONTAINS Tests ---
# def test_contains():
#     t = "aba"
#     assert check("CONTAINS", t, "aba") is True      
#     assert check("CONTAINS", t, "babac") is True    
#     assert check("CONTAINS", t, "ab") is False      
#     assert check("CONTAINS", t, "") is False

# # --- 4. NEGATION Tests ---
# def test_not_starts_with():
#     assert check("NOT_STARTS_WITH", "b", "a") is True
#     assert check("NOT_STARTS_WITH", "b", "") is True 
#     assert check("NOT_STARTS_WITH", "b", "b") is False

# def test_not_contains():
#     assert check("NOT_CONTAINS", "aa", "aba") is True
#     assert check("NOT_CONTAINS", "aa", "baab") is False

# # --- 5. EDGE CASE: Empty Target ---
# def test_empty_target_behavior():
    # assert check("STARTS_WITH", "", "abc") is True
    # assert check("CONTAINS", "", "abc") is True