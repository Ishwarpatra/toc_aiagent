from __future__ import annotations

import re
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, model_validator, ConfigDict

# Improved LogicSpec and DFA models.
# - Enhanced natural-language atomic parser (more patterns: length, length mod, count mod).
# - Pydantic V2 model_validator used instead of deprecated V1 @validator.
# - Uses future annotations to avoid update_forward_refs deprecation.

class LogicSpec(BaseModel):
    logic_type: str
    target: Optional[str] = None
    alphabet: List[str] = Field(default_factory=lambda: ["0", "1"])
    children: List["LogicSpec"] = Field(default_factory=list)
    reasoning: Optional[str] = None

    # Pydantic V2 model configuration
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def from_prompt(cls, user_prompt: str) -> Optional["LogicSpec"]:
        """
        Heuristic atomic parser:
        - Detects atomic types including:
            STARTS_WITH, ENDS_WITH, CONTAINS, NOT_CONTAINS, NO_CONSECUTIVE,
            DIVISIBLE_BY, ODD_COUNT, EVEN_COUNT,
            EXACT_LENGTH, MIN_LENGTH, MAX_LENGTH, LENGTH_MOD, COUNT_MOD, PRODUCT_EVEN.
        - Extracts targets from quoted or unquoted forms (alphanumeric)
        - Derives alphabet from the extracted target when possible.
        - Special case: single-letter targets default to a binary pair:
            'a' -> ['a','b'], '0' -> ['0','1']
        """
        if not user_prompt:
            return None

        user_lower = user_prompt.lower()

        # If prompt appears composite, bail out here (AnalystAgent will handle)
        if " and " in user_lower or " or " in user_lower:
            return None

        deduced_type = None
        deduced_target = None
        deduced_alphabet = ["0", "1"]

        # --- LENGTH-based patterns ---
        # exact: "length is 5", "strings of length 5", "length = 5"
        m = re.search(r"(?:length|len)(?:\s*(?:is|=)|\s+of\s+length\s+|\s*)\s*(\d+)\b", user_lower)
        if m:
            deduced_type = "EXACT_LENGTH"
            deduced_target = m.group(1)
            return cls(logic_type=deduced_type, target=deduced_target, alphabet=deduced_alphabet)

        # min length: "length >= 3", "at least 3 characters", "minimum length 3"
        m = re.search(r"(?:at least|min(?:imum)?\s*length|length\s*(?:>=|>=\s*|>=\s*))\s*(\d+)\b", user_lower)
        if m:
            deduced_type = "MIN_LENGTH"
            deduced_target = m.group(1)
            return cls(logic_type=deduced_type, target=deduced_target, alphabet=deduced_alphabet)

        # max length: "length <= 7", "at most 7 characters", "maximum length 7"
        m = re.search(r"(?:at most|max(?:imum)?\s*length|length\s*(?:<=|<=\s*|<=\s*))\s*(\d+)\b", user_lower)
        if m:
            deduced_type = "MAX_LENGTH"
            deduced_target = m.group(1)
            return cls(logic_type=deduced_type, target=deduced_target, alphabet=deduced_alphabet)

        # length mod: "length mod 3 = 1", "len % 3 == 1", "length modulo 3 is 1"
        m = re.search(r"(?:length|len)\s*(?:mod|%|modulo)\s*(\d+)\s*(?:=|==|equals|is)?\s*(\d+)", user_lower)
        if m:
            k, r = m.group(1), m.group(2)
            deduced_type = "LENGTH_MOD"
            # target format: "r:k"
            deduced_target = f"{r}:{k}"
            return cls(logic_type=deduced_type, target=deduced_target, alphabet=deduced_alphabet)

        # --- COUNT-based patterns ---
        # count mod: "count of 1s mod 3 = 2", "number of 'a' mod 4 is 1"
        m = re.search(
            r"(?:count of|number of|# of)?\s*['\"]?([0-9a-zA-Z])['\"]?s?\s*(?:count)?\s*(?:mod|%|modulo)\s*(\d+)\s*(?:=|==|equals|is)?\s*(\d+)",
            user_lower)
        if m:
            sym, k, r = m.group(1), m.group(2), m.group(3)
            deduced_type = "COUNT_MOD"
            # target format: "symbol:r:k"
            deduced_target = f"{sym}:{r}:{k}"
            # derive alphabet conservatively
            if re.search(r"[a-zA-Z]", sym):
                deduced_alphabet = [sym, 'b' if sym != 'b' else 'a']
            return cls(logic_type=deduced_type, target=deduced_target, alphabet=deduced_alphabet)

        # Even/Odd count shorthand: 
        # Handles: "even number of 1s", "odd number of 0", "odd count of 1", "even number of 'a's"
        # Pattern breakdown:
        #   (odd|even) - parity word
        #   \s+(number|count)\s+of\s+ - "number of" or "count of"
        #   ['\"]? - optional opening quote
        #   ([0-9a-zA-Z]) - the character to count
        #   ['\"]? - optional closing quote
        #   s? - optional trailing 's' (for plurals like "1s" or "a's")
        parity_match = re.search(
            r"(odd|even)\s+(?:number|count)\s+of\s+['\"]?([0-9a-zA-Z])['\"]?s?",
            user_lower
        )
        if parity_match:
            ptype, char = parity_match.groups()
            deduced_type = "ODD_COUNT" if ptype == "odd" else "EVEN_COUNT"
            deduced_target = char
            deduced_alphabet = ['0', '1'] if char in '01' else [char, 'b' if char != 'b' else 'a']
            return cls(logic_type=deduced_type, target=deduced_target, alphabet=deduced_alphabet)

        # Parity product: "product is even", "product even"
        if re.search(r"product\s+(?:is\s+)?even", user_lower):
            return cls(logic_type="PRODUCT_EVEN", target=None, alphabet=deduced_alphabet)
        if re.search(r"product\s+(?:is\s+)?odd", user_lower):
            # There isn't an explicit PRODUCT_ODD builder; handle by NOT(PRODUCT_EVEN) in composed specs
            return cls(logic_type="PRODUCT_ODD", target=None, alphabet=deduced_alphabet)

        # Divisible by (numeric)
        if "divisible by" in user_lower:
            deduced_type = "DIVISIBLE_BY"
            div_match = re.search(r"divisible\s+by\s+(\d+)", user_lower)
            if div_match:
                deduced_target = div_match.group(1)
                return cls(logic_type=deduced_type, target=deduced_target, alphabet=deduced_alphabet)

        # No consecutive
        if "no consecutive" in user_lower or "does not contain consecutive" in user_lower:
            deduced_type = "NO_CONSECUTIVE"
            char_match = re.search(r"consecutive\s+['\"]?([0-9a-zA-Z])['\"]?s?", user_lower)
            deduced_target = char_match.group(1) if char_match else "1"
            if re.search(r"[a-zA-Z]", deduced_target):
                deduced_alphabet = [deduced_target, 'b' if deduced_target != 'b' else 'a']
            return cls(logic_type=deduced_type, target=deduced_target, alphabet=deduced_alphabet)

        # Negations / basic patterns
        # Negations / basic patterns with improved typo-robustness
        if re.search(r"not\s+st[art]{2,}s?|does\s+not\s+st[art]{2,}s?", user_lower):
            deduced_type = "NOT_STARTS_WITH"
        elif re.search(r"st[art]{2,}s?|beg[in]{2,}s?", user_lower):
            deduced_type = "STARTS_WITH"
        elif re.search(r"not\s+en[ds]{1,}|does\s+not\s+en[ds]{1,}", user_lower):
            deduced_type = "NOT_ENDS_WITH"
        elif re.search(r"en[ds]{1,2}\b", user_lower):
            deduced_type = "ENDS_WITH"
        elif re.search(r"not\s+cont[ain]{2,}|does\s+not\s+cont[ain]{2,}", user_lower):
            deduced_type = "NOT_CONTAINS"
        elif re.search(r"cont[ain]{2,}s?|incl[ude]{2,}s?", user_lower):
            deduced_type = "CONTAINS"

        # If we have an atomic type that expects a target, extract it
        if deduced_type and deduced_type not in ["DIVISIBLE_BY", "ODD_COUNT", "EVEN_COUNT", "PRODUCT_EVEN", "PRODUCT_ODD"]:
            # Try quoted targets first (e.g., 'ab', "01")
            quote_match = re.search(r"['\"]([0-9a-zA-Z]+)['\"]", user_lower)
            if quote_match:
                deduced_target = quote_match.group(1)
            else:
                # Try unquoted pattern like "starts with ab" or "contains 01"
                unquoted_match = re.search(r"(?:with|contains?)\s+([0-9a-zA-Z]+)\b", user_lower)
                if unquoted_match:
                    deduced_target = unquoted_match.group(1)

        # If we have a target, derive alphabet conservatively
        if deduced_target:
            if re.search(r"[a-zA-Z]", deduced_target):
                letters = [c for c in deduced_target if c.isalpha()]
                if len(set(letters)) == 1:
                    single = letters[0]
                    pair = 'b' if single.isalpha() else '1'
                    deduced_alphabet = [single, pair]
                else:
                    deduced_alphabet = sorted(list(dict.fromkeys(letters)))
            elif re.fullmatch(r"[01]+", deduced_target):
                deduced_alphabet = ['0', '1']
            elif deduced_target.isdigit():
                deduced_alphabet = sorted(list(dict.fromkeys([c for c in deduced_target if c.isdigit()])))
            return cls(logic_type=deduced_type, target=deduced_target, alphabet=deduced_alphabet)

        # No atomic match
        return None


class DFA(BaseModel):
    reasoning: Optional[str] = ""
    states: List[str]
    alphabet: List[str]
    transitions: Dict[str, Dict[str, str]]
    start_state: str
    accept_states: List[str]

    model_config = ConfigDict()

    @model_validator(mode="after")
    def validate_integrity(self):
        if self.start_state not in self.states:
            raise ValueError("Empty or invalid start_state")
        return self

    def accepts(self, input_string: str) -> bool:
        """
        Simulate the DFA on the given input string.
        
        Returns True if the string is accepted (ends in an accept state),
        False if rejected or if any character causes a crash (missing transition).
        
        This is the core method for Black Box testing - it only uses the DFA's
        structure, not any external specification.
        """
        current_state = self.start_state
        
        for char in input_string:
            # Check if character is in alphabet
            if char not in self.alphabet:
                return False  # Invalid character, reject
            
            # Check for valid transition
            if current_state not in self.transitions:
                return False  # No transitions from current state, crash
            
            if char not in self.transitions[current_state]:
                return False  # No transition for this character, crash
            
            current_state = self.transitions[current_state][char]
        
        return current_state in self.accept_states
    
    def simulate_with_trace(self, input_string: str) -> dict:
        """
        Simulate the DFA with a full trace for debugging purposes.
        
        Returns a dictionary with:
        - accepted: bool
        - trace: list of (state, char, next_state) tuples
        - final_state: the ending state (or None if crashed)
        - crash_reason: reason for crash if any
        """
        trace = []
        current_state = self.start_state
        
        for i, char in enumerate(input_string):
            if char not in self.alphabet:
                return {
                    "accepted": False,
                    "trace": trace,
                    "final_state": None,
                    "crash_reason": f"Invalid character '{char}' at position {i}"
                }
            
            if current_state not in self.transitions:
                return {
                    "accepted": False,
                    "trace": trace,
                    "final_state": None,
                    "crash_reason": f"No transitions from state '{current_state}'"
                }
            
            if char not in self.transitions[current_state]:
                return {
                    "accepted": False,
                    "trace": trace,
                    "final_state": None,
                    "crash_reason": f"No transition for '{char}' from state '{current_state}'"
                }
            
            next_state = self.transitions[current_state][char]
            trace.append((current_state, char, next_state))
            current_state = next_state
        
        return {
            "accepted": current_state in self.accept_states,
            "trace": trace,
            "final_state": current_state,
            "crash_reason": None
        }

    def model_dump(self) -> Dict[str, Any]:
        return {
            "states": self.states,
            "alphabet": self.alphabet,
            "transitions": self.transitions,
            "start_state": self.start_state,
            "accept_states": self.accept_states,
            "reasoning": self.reasoning,
        }