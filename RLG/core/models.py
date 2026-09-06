from pydantic import BaseModel, Field
from typing import List, Dict, Set

class DFA(BaseModel):
    states: Set[str]
    alphabet: Set[str]
    transitions: Dict[str, Dict[str, str]]
    start_state: str
    accept_states: Set[str]

class DeterministicValidator:
    @staticmethod
    def validate(dfa: DFA) -> bool:
        # Basic validation for DFA consistency
        if dfa.start_state not in dfa.states:
            return False
        if not dfa.accept_states.issubset(dfa.states):
            return False
        for state, transitions in dfa.transitions.items():
            if state not in dfa.states:
                return False
            for char, next_state in transitions.items():
                if char not in dfa.alphabet:
                    return False
                if next_state not in dfa.states:
                    return False
        return True
