from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Optional
import re

class LogicSpec(BaseModel):
    logic_type: str = Field(..., description="Enum: STARTS_WITH, NOT_STARTS_WITH, ENDS_WITH, NOT_ENDS_WITH, CONTAINS, NOT_CONTAINS, DIVISIBLE_BY, NO_CONSECUTIVE, ODD_COUNT, EVEN_COUNT")
    target: str = Field(..., description="The substring required (e.g., 'aba', 'b') or number")
    alphabet: List[str] = Field(default=['0', '1'])

    @classmethod
    def from_prompt(cls, user_prompt: str) -> Optional['LogicSpec']:
        """
        Attempts to extract a LogicSpec from a natural language prompt using regex heuristics.
        """
        user_lower = user_prompt.lower()
        deduced_type = None
        deduced_target = None

        # Parity Logic
        parity_match = re.search(r"(odd|even)\s+number\s+of\s+['\"]?([01])['\"]?s?", user_lower)
        if parity_match:
            ptype, digit = parity_match.groups()
            deduced_type = "ODD_COUNT" if ptype == "odd" else "EVEN_COUNT"
            deduced_target = digit

        # Divisibility Logic
        elif "divisible by" in user_lower:
            deduced_type = "DIVISIBLE_BY"
            div_match = re.search(r"divisible\s+by\s+(\d+)", user_lower)
            if div_match:
                deduced_target = div_match.group(1)

        # Standard String Logic
        elif "no consecutive" in user_lower: 
            deduced_type = "NO_CONSECUTIVE"
            char_match = re.search(r"consecutive\s+['\"]?([01])['\"]?s?", user_lower)
            deduced_target = char_match.group(1) if char_match else "1"
        elif "not start" in user_lower or "does not start" in user_lower: deduced_type = "NOT_STARTS_WITH"
        elif "start" in user_lower or "begin" in user_lower: deduced_type = "STARTS_WITH"
        elif "not end" in user_lower or "does not end" in user_lower: deduced_type = "NOT_ENDS_WITH"
        elif "end" in user_lower: deduced_type = "ENDS_WITH"
        elif "not contain" in user_lower: deduced_type = "NOT_CONTAINS"
        elif "contain" in user_lower: deduced_type = "CONTAINS"

        # Target Extraction
        if deduced_type and not deduced_target:
            match = re.search(r"['\"](.*?)['\"]", user_prompt)
            if not match: 
                match = re.search(r"\b[01a-zA-Z]+\b$", user_prompt)
            if match: 
                deduced_target = match.group(0).strip("'\"")

        if deduced_type and deduced_target:
            return cls(logic_type=deduced_type, target=deduced_target)
        
        return None

# --- EXISTING DFA MODEL ---
class DFA(BaseModel):
    reasoning: str = Field(default="", description="Step-by-step logic.")
    states: List[str]
    alphabet: List[str]
    transitions: Dict[str, Dict[str, str]]
    start_state: str
    accept_states: List[str]

    @model_validator(mode='after')
    def validate_integrity(self):
        if self.start_state not in self.states:
            # Auto-patch if possible, otherwise raise
            if not self.states: raise ValueError("Empty state list")
            
        for state in self.states:
            if state not in self.transitions:
                continue # Allow partials, repair engine will fix
        return self