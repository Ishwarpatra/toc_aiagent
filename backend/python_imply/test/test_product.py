import pytest
from pydantic import BaseModel
from core.product import ProductConstructionEngine
from core.models import DFA, LogicSpec
from main import DFAGeneratorSystem
from core.validator import DeterministicValidator
from core.agents import AnalystAgent, ArchitectAgent, BaseAgent 

base = BaseAgent()
agent = AnalystAgent(base)

def test_prompt1():
    spec = agent.analyze("Design a DFA that accepts strings starting with 'a'")
    assert spec.logic_type == "STARTS_WITH"
    print(spec.target)
    assert spec.target == "a"

def test_prompt2():
    spec = agent.analyze("Design a DFA that accepts strings ending with 'a'")
    assert spec.logic_type == "ENDS_WITH"
    print(spec.target)
    assert spec.target == "a"
    
def test_prompt3():
    spec = agent.analyze("Design a DFA that accepts strings starting with '0'")
    assert spec.logic_type == "STARTS_WITH"
    print(spec.target)
    assert spec.target == "0"
    
def test_prompt4():
    spec = agent.analyze("Design a DFA that accepts strings starting with '1'")
    assert spec.logic_type == "STARTS_WITH"
    print(spec.target)
    assert spec.target == "1"


import json
from unittest.mock import patch

from core.agents import AnalystAgent


def test_composite_starts_with_a_and_ends_with_b():
    """
    Tests composite logic parsing:
    STARTS_WITH 'a' AND ENDS_WITH 'b'
    """

    # --- Fake LLM response (INTENTIONALLY uses type/constraints) ---
    fake_llm_response = json.dumps({
        "type": "AND",
        "constraints": [
            {
                "type": "STARTS_WITH",
                "target": "a"
            },
            {
                "type": "ENDS_WITH",
                "target": "b"
            }
        ]
    })

    # analyst = AnalystAgent()

    # prompt = "Design a DFA that accepts strings starts with 'a' AND ends with 'b'"

    # # --- Mock Ollama call ---
    # with patch.object(
    #     analyst,
    #     "call_ollama",
    #     return_value=fake_llm_response
    # ):
    #     spec = analyst.analyze(prompt)

    # # --- Assertions ---
    # assert isinstance(spec, LogicSpec)

    # # Root logic
    # assert spec.logic_type == "AND"
    # assert spec.target is None
    # assert len(spec.children) == 2

    # # Child 1
    # c1 = spec.children[0]
    # assert c1.logic_type == "STARTS_WITH"
    # assert c1.target == "a"
    # assert c1.alphabet == ["a", "b"]

    # # Child 2
    # c2 = spec.children[1]
    # assert c2.logic_type == "ENDS_WITH"
    # assert c2.target == "b"
    # assert c2.alphabet == ["a", "b"]

    
# spec = agent.analyze("Design a DFA that accepts strings starting with 'a'")

# def test_prompt1():
#     assert spec.logic_type == "STARTS_WITH"
#     print(spec.target)
#     assert spec.target == "a"
    
architect = ArchitectAgent(base)

from unittest.mock import patch
import json

def test_architect_starts_with_a():
    spec = agent.analyze("Design a DFA that accepts strings starting with 'a'")
    fake_response = json.dumps({
        "states": ["q0", "q1", "q_dead"],
        "start_state": "q0",
        "accept_states": ["q1"],
        "transitions": {
            "q0": {"a": "q1", "b": "q_dead"},
            "q1": {"a": "q1", "b": "q1"},
            "q_dead": {"a": "q_dead", "b": "q_dead"}
        }
    })

    with patch("core.agents.ArchitectAgent.call_ollama", return_value=fake_response):
        dfa = architect.design(spec)
        assert dfa.start_state == "q0"
        assert dfa.accept_states == ["q1"]
        print(dfa.transitions)
        

def test_architect_ends_with_b():
    spec = agent.analyze("Design a DFA that accepts strings ending with 'b'")
    fake_response = json.dumps({
        "states": ["q0", "q1"],
        "start_state": "q0",
        "accept_states": ["q1"],
        "transitions": {
            "q0": {"a": "q0", "b": "q1"},
            "q1": {"a": "q0", "b": "q1"}
        }
    })

    with patch("core.agents.ArchitectAgent.call_ollama", return_value=fake_response):
        dfa = architect.design(spec)
        assert dfa.start_state == "q0"
        assert dfa.accept_states == ["q1"]
        print(dfa.transitions)

def test_architect_ends_with_0():
    spec = agent.analyze("Design a DFA that accepts strings ending with '0'")

    fake_response = json.dumps({
        "states": ["q0", "q1"],
        "start_state": "q0",
        "accept_states": ["q1"],
        "transitions": {
            "q0": {"0": "q1", "1": "q0"},
            "q1": {"0": "q1", "1": "q0"}
        }
    })

    with patch("core.agents.ArchitectAgent.call_ollama", return_value=fake_response):
        dfa = architect.design(spec)

        assert dfa.start_state == "q0"
        assert dfa.accept_states == ["q1"]
        assert dfa.transitions["q0"]["0"] == "q1"
        assert dfa.transitions["q1"]["1"] == "q0"

        print(dfa.transitions)


def test_architect_starts_with_0():
    spec = agent.analyze("Design a DFA that accepts strings starting with '0'")

    fake_response = json.dumps({
        "states": ["q0", "q1", "q2"],
        "start_state": "q0",
        "accept_states": ["q1"],
        "transitions": {
            "q0": {"0": "q1", "1": "q2"},
            "q1": {"0": "q1", "1": "q1"},
            "q2": {"0": "q2", "1": "q2"}
        }
    })

    with patch("core.agents.ArchitectAgent.call_ollama", return_value=fake_response):
        dfa = architect.design(spec)

        assert dfa.start_state == "q0"
        assert dfa.accept_states == ["q1"]
        assert dfa.transitions["q0"]["0"] == "q1"
        assert dfa.transitions["q0"]["1"] == "q2"

        print(dfa.transitions)



# # Helper to create simple DFAs
# def create_starts_with_a():
#     return DFA(
#         reasoning="Starts with a",
#         states=["q0", "q1", "q_dead"],
#         alphabet=["a", "b"],
#         transitions={
#             "q0": {"a": "q1", "b": "q_dead"},
#             "q1": {"a": "q1", "b": "q1"},
#             "q_dead": {"a": "q_dead", "b": "q_dead"}
#         },
#         start_state="q0",
#         accept_states=["q1"]
#     )

# def create_ends_with_b():
#     return DFA(
#         reasoning="Ends with b",
#         states=["q0", "q1"],
#         alphabet=["a", "b"],
#         transitions={
#             "q0": {"a": "q0", "b": "q1"},
#             "q1": {"a": "q0", "b": "q1"}
#         },
#         start_state="q0",
#         accept_states=["q1"]
#     )

# def test_product_intersection():
#     engine = ProductConstructionEngine()
#     dfa1 = create_starts_with_a()
#     dfa2 = create_ends_with_b()
    
#     # "Starts with A" AND "Ends with B"
#     # Should accept: "ab", "aab", "abb"
#     # Should reject: "a" (ends with a), "b" (starts with b), "ba"
    
#     combined = engine.combine(dfa1, dfa2, "AND")
    
#     # Check Acceptance
#     def simulate(s):
#         curr = combined.start_state
#         for char in s:
#             curr = combined.transitions.get(curr, {}).get(char, "dead")
#         return curr in combined.accept_states
        
#     assert simulate("ab") is True
#     assert simulate("aab") is True
#     assert simulate("abb") is True
#     assert simulate("a") is False
#     assert simulate("b") is False
#     assert simulate("ba") is False
    
#     print("\nIntersection Test Passed!")

# def test_product_union():
#     engine = ProductConstructionEngine()
#     dfa1 = create_starts_with_a()
#     dfa2 = create_ends_with_b()
    
#     # "Starts with A" OR "Ends with B"
#     # Should accept: "a" (starts with a), "b" (ends with b), "ab" (both)
#     # Should reject: "c" (if alphabet allowed), "ba" (starts b, ends a) -> Wait.
#     # "ba": Starts with B (False) OR Ends with A (False) -> Reject.
    
#     combined = engine.combine(dfa1, dfa2, "OR")
    
#     def simulate(s):
#         curr = combined.start_state
#         for char in s:
#             curr = combined.transitions.get(curr, {}).get(char, "dead")
#         return curr in combined.accept_states
        
#     assert simulate("a") is True
#     assert simulate("ab") is True
#     assert simulate("b") is True
#     assert simulate("ba") is False
    
#     print("Union Test Passed!")