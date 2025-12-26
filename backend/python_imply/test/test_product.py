import pytest
from core.product import ProductConstructionEngine
from core.models import DFA

# Helper to create simple DFAs
def create_starts_with_a():
    return DFA(
        reasoning="Starts with a",
        states=["q0", "q1", "q_dead"],
        alphabet=["a", "b"],
        transitions={
            "q0": {"a": "q1", "b": "q_dead"},
            "q1": {"a": "q1", "b": "q1"},
            "q_dead": {"a": "q_dead", "b": "q_dead"}
        },
        start_state="q0",
        accept_states=["q1"]
    )

def create_ends_with_b():
    return DFA(
        reasoning="Ends with b",
        states=["q0", "q1"],
        alphabet=["a", "b"],
        transitions={
            "q0": {"a": "q0", "b": "q1"},
            "q1": {"a": "q0", "b": "q1"}
        },
        start_state="q0",
        accept_states=["q1"]
    )

def test_product_intersection():
    engine = ProductConstructionEngine()
    dfa1 = create_starts_with_a()
    dfa2 = create_ends_with_b()
    
    # "Starts with A" AND "Ends with B"
    # Should accept: "ab", "aab", "abb"
    # Should reject: "a" (ends with a), "b" (starts with b), "ba"
    
    combined = engine.combine(dfa1, dfa2, "AND")
    
    # Check Acceptance
    def simulate(s):
        curr = combined.start_state
        for char in s:
            curr = combined.transitions.get(curr, {}).get(char, "dead")
        return curr in combined.accept_states
        
    assert simulate("ab") is True
    assert simulate("aab") is True
    assert simulate("abb") is True
    assert simulate("a") is False
    assert simulate("b") is False
    assert simulate("ba") is False
    
    print("\nIntersection Test Passed!")

def test_product_union():
    engine = ProductConstructionEngine()
    dfa1 = create_starts_with_a()
    dfa2 = create_ends_with_b()
    
    # "Starts with A" OR "Ends with B"
    # Should accept: "a" (starts with a), "b" (ends with b), "ab" (both)
    # Should reject: "c" (if alphabet allowed), "ba" (starts b, ends a) -> Wait.
    # "ba": Starts with B (False) OR Ends with A (False) -> Reject.
    
    combined = engine.combine(dfa1, dfa2, "OR")
    
    def simulate(s):
        curr = combined.start_state
        for char in s:
            curr = combined.transitions.get(curr, {}).get(char, "dead")
        return curr in combined.accept_states
        
    assert simulate("a") is True
    assert simulate("ab") is True
    assert simulate("b") is True
    assert simulate("ba") is False
    
    print("Union Test Passed!")