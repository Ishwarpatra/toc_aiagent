from pydantic import BaseModel, Field, model_validator
from typing import List, Dict

class DFA(BaseModel):
    # This field allows the AI to "think out loud" before writing the complex math
    reasoning: str = Field(..., description="Step-by-step logic for constructing the states and transitions.")
    
    states: List[str] = Field(..., description="List of all state names")
    alphabet: List[str] = Field(..., description="Allowed symbols")
    transitions: Dict[str, Dict[str, str]] = Field(..., description="Map of state -> symbol -> next_state")
    start_state: str
    accept_states: List[str]

    @model_validator(mode='after')
    def validate_integrity(self):
        # 1. Check start state  
        if self.start_state not in self.states:
            raise ValueError(f"Start state '{self.start_state}' is not in state list.")
        
        # 2. Check transitions
        for state in self.states:
            if state not in self.transitions:
                raise ValueError(f"State '{state}' is missing from the transition table.")
            
            for symbol in self.alphabet:
                if symbol not in self.transitions[state]:
                    raise ValueError(f"State '{state}' has no transition for symbol '{symbol}'.")
                
                dest = self.transitions[state][symbol]
                if dest not in self.states:
                    raise ValueError(f"State '{state}' transitions to unknown state '{dest}'.")
                    
        return self