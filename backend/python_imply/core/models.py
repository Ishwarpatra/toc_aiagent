from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Optional, ForwardRef
import re

# Recursive Type Definition
LogicSpecRef = ForwardRef('LogicSpec')

class LogicSpec(BaseModel):
    logic_type: str = Field(..., description="Atomic types or Composite (AND, OR, NOT)")
    target: Optional[str] = Field(None, description="Target for atomic types")
    alphabet: List[str] = Field(default=['0', '1'])
    children: List[LogicSpecRef] = Field(default=[], description="Sub-constraints")

    def set_alphabet_recursive(self, new_alphabet: List[str]):
        """
        Forces this spec and all its children to use the specified alphabet.
        """
        self.alphabet = new_alphabet
        if self.children:
            for child in self.children:
                child.set_alphabet_recursive(new_alphabet)
    @classmethod
    def from_prompt(cls, user_prompt: str) -> Optional['LogicSpec']:
        user_lower = user_prompt.lower()
        
        # --- 1. DETECT COMPOSITE LOGIC (Simple Heuristic) ---
        # If we see " and " or " or ", we defer to the LLM (AnalystAgent) 
        # because regex splitting is too brittle for complex natural language.
        if " and " in user_lower or " or " in user_lower:
            return None # AnalystAgent will handle this via LLM

        # --- 2. DETECT ALPHABET ---
        deduced_alphabet = ['0', '1']
        if re.search(r"['\"]a['\"]", user_lower) or re.search(r"['\"]b['\"]", user_lower):
             deduced_alphabet = ['a', 'b']

        # --- 3. ATOMIC EXTRACTION (Optimized) ---
        deduced_type = None
        deduced_target = None

        # Parity
        parity_match = re.search(r"(odd|even)\s+number\s+of\s+['\"]?([01ab])['\"]?s?", user_lower)
        if parity_match:
            ptype, char = parity_match.groups()
            deduced_type = "ODD_COUNT" if ptype == "odd" else "EVEN_COUNT"
            deduced_target = char

        # Divisibility
        elif "divisible by" in user_lower:
            deduced_type = "DIVISIBLE_BY"
            div_match = re.search(r"divisible\s+by\s+(\d+)", user_lower)
            if div_match: deduced_target = div_match.group(1)

        # Standard Patterns
        elif "no consecutive" in user_lower: 
            deduced_type = "NO_CONSECUTIVE"
            char_match = re.search(r"consecutive\s+['\"]?([01ab])['\"]?s?", user_lower)
            deduced_target = char_match.group(1) if char_match else "1"
        elif "not start" in user_lower: deduced_type = "NOT_STARTS_WITH"
        elif "start" in user_lower: deduced_type = "STARTS_WITH"
        elif "not end" in user_lower: deduced_type = "NOT_ENDS_WITH"
        elif "end" in user_lower: deduced_type = "ENDS_WITH"
        elif "not contain" in user_lower: deduced_type = "NOT_CONTAINS"
        elif "contain" in user_lower: deduced_type = "CONTAINS"

        # Regex Target Extraction
        if not deduced_target and deduced_type and deduced_type not in ["DIVISIBLE_BY", "ODD_COUNT", "EVEN_COUNT"]:
             quote_match = re.search(r"['\"]([01ab]+)['\"]", user_lower)
             if quote_match: deduced_target = quote_match.group(1)

        if deduced_type and deduced_target:
            if re.search(r"[a-z]", deduced_target): deduced_alphabet = ['a', 'b']
            return cls(logic_type=deduced_type, target=deduced_target, alphabet=deduced_alphabet)

        return None

LogicSpec.model_rebuild()

class DFA(BaseModel):
    reasoning: str = Field(default="")
    states: List[str]
    alphabet: List[str]
    transitions: Dict[str, Dict[str, str]]
    start_state: str
    accept_states: List[str]

    @model_validator(mode='after')
    def validate_integrity(self):
        if self.start_state not in self.states:
            if not self.states: raise ValueError("Empty state list")
        return self