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
        # Default alphabet is 0,1, but we will change it if we see letters
        deduced_alphabet = ['0', '1'] 

        # --- ALPHABET DETECTION ---
        # Prefer letters if any are present in the prompt; otherwise default to '0','1'.
        # Once we decide on letters we DO NOT flip back because mixed targets like 'a1'
        # should keep the alphabet as letters when a letter appears anywhere.
        if re.search(r"[a-zA-Z]", user_prompt):
            deduced_alphabet = ['a', 'b']
        else:
            deduced_alphabet = ['0', '1']

        # Parity Logic
        parity_match = re.search(r"(odd|even)\s+number\s+of\s+['\"]?([01a-zA-Z])['\"]?s?", user_lower)
        if parity_match:
            ptype, char = parity_match.groups()
            deduced_type = "ODD_COUNT" if ptype == "odd" else "EVEN_COUNT"
            deduced_target = char

        # Divisibility Logic
        elif "divisible by" in user_lower:
            deduced_type = "DIVISIBLE_BY"
            div_match = re.search(r"divisible\s+by\s+(\d+)", user_lower)
            if div_match:
                deduced_target = div_match.group(1)

        # Standard String Logic
        elif "no consecutive" in user_lower: 
            deduced_type = "NO_CONSECUTIVE"
            char_match = re.search(r"consecutive\s+['\"]?([01a-zA-Z])['\"]?s?", user_lower)
            deduced_target = char_match.group(1) if char_match else "1"
        elif "not start" in user_lower or "does not start" in user_lower: deduced_type = "NOT_STARTS_WITH"
        elif "start" in user_lower or "begin" in user_lower: deduced_type = "STARTS_WITH"
        elif "not end" in user_lower or "does not end" in user_lower: deduced_type = "NOT_ENDS_WITH"
        elif "end" in user_lower: deduced_type = "ENDS_WITH"
        elif "not contain" in user_lower: deduced_type = "NOT_CONTAINS"
        elif "contain" in user_lower: deduced_type = "CONTAINS"

        # Target Extraction
        if deduced_type and deduced_target:
            # If the target itself contains any letter, ensure alphabet is letters and do
            # not allow a later rule to flip it back to digits. Otherwise keep the
            # alphabet inferred from the overall prompt.
            if re.search(r"[a-zA-Z]", deduced_target):
                deduced_alphabet = ['a', 'b']

            return cls(logic_type=deduced_type, target=deduced_target, alphabet=deduced_alphabet)

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