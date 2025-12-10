import re
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

# --- Shared Data Models ---

class LogicSpec(BaseModel):
    logic_type: str = Field(..., description="Enum: STARTS_WITH, NOT_STARTS_WITH, ENDS_WITH, NOT_ENDS_WITH, CONTAINS, NOT_CONTAINS, DIVISIBLE_BY, NO_CONSECUTIVE, ODD_COUNT, EVEN_COUNT")
    target: str = Field(..., description="The substring required (e.g., 'aba', 'b') or number")
    alphabet: List[str] = Field(default=['0', '1'])

    @classmethod
    def from_prompt(cls, user_prompt: str) -> Optional['LogicSpec']:
        """
        Attempts to extract a LogicSpec from a natural language prompt using regex heuristics.
        Returns None if no specific pattern is matched, allowing the caller (Agent) to fallback to LLM.
        """
        user_lower = user_prompt.lower()
        deduced_type = None
        deduced_target = None

        # --- PRECISE REGEX HEURISTICS ---
        
        # Parity Logic: "odd number of 0s", "even number of 1's"
        parity_match = re.search(r"(odd|even)\s+number\s+of\s+['\"]?([01])['\"]?s?", user_lower)
        if parity_match:
            ptype, digit = parity_match.groups()
            deduced_type = "ODD_COUNT" if ptype == "odd" else "EVEN_COUNT"
            deduced_target = digit

        # Divisibility Logic: "divisible by 3"
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

        # Attempt to find target if logic was found but target wasn't obvious
        if deduced_type and not deduced_target:
            # Look for quotes first: 'bb'
            match = re.search(r"['\"](.*?)['\"]", user_prompt)
            if not match: 
                # Fallback to simple words/digits at the end
                match = re.search(r"\b[01a-zA-Z]+\b$", user_prompt)
            if match: 
                deduced_target = match.group(0).strip("'\"")

        if deduced_type and deduced_target:
            return cls(logic_type=deduced_type, target=deduced_target)
        
        return None

class DFA(BaseModel):
    states: List[str]
    alphabet: List[str]
    transitions: Dict[str, Dict[str, str]]
    start_state: str
    accept_states: List[str]
    reasoning: str = Field(default="", description="Explain the logic.")

# --- The Truth Engine ---

class DeterministicValidator:
    def validate(self, dfa: DFA, spec: LogicSpec) -> tuple[bool, str]:
        """
        Runs the DFA against the truth function.
        """
        print(f"\n[Validator] Running Checks for {spec.logic_type} '{spec.target}'...")
        
        # 1. Generate Test Cases
        test_inputs = ["", "0", "1", "00", "01", "10", "11"]
        if spec.target:
            t = spec.target
            test_inputs.extend([t, t+"0", "0"+t, "1"+t+"0"])
            if len(t) > 1: test_inputs.append(t[:-1])
            # For numeric/parity logic, add more variety
            if spec.logic_type in ["DIVISIBLE_BY", "ODD_COUNT", "EVEN_COUNT"]:
                test_inputs.extend(["000", "111", "1010", "0101", "1100", "0011"])
        
        test_inputs = sorted(list(set(test_inputs)))
        error_log = []

        # 2. Validation Loop
        for s in test_inputs:
            if any(c not in dfa.alphabet for c in s): continue
            
            # Use public get_truth
            expected = self.get_truth(s, spec)
            
            try:
                actual = self._simulate_dfa(dfa, s)
            except Exception as e:
                return False, f"Simulation Crashed: {e}"
            
            if expected != actual:
                verdict = "ACCEPTED" if actual else "REJECTED"
                should_be = "ACCEPT" if expected else "REJECT"
                error_log.append(f"FAIL: Input '{s}' was {verdict} (Expected {should_be})")

        if not error_log:
            print("   -> ALL TESTS PASSED.")
            return True, "Passed"
        else:
            feedback = "\n".join(error_log[:3])
            print(f"   -> FAILURES FOUND:\n{feedback}")
            return False, feedback

    def get_truth(self, s: str, spec: LogicSpec) -> bool:
        """
        Public Truth Function. Verified by Pytest.
        """
        t = spec.target
        lt = spec.logic_type
        
        # String Logic
        if lt == "STARTS_WITH": return s.startswith(t)
        if lt == "NOT_STARTS_WITH": return not s.startswith(t)
        if lt == "ENDS_WITH": return s.endswith(t)
        if lt == "NOT_ENDS_WITH": return not s.endswith(t)
        if lt == "CONTAINS": return t in s
        if lt == "NOT_CONTAINS": return t not in s
        if lt == "NO_CONSECUTIVE": return t*2 not in s 
        
        # Numeric/Count Logic
        if lt == "DIVISIBLE_BY":
            if not s: return False 
            try:
                num = int(s, 2)
                return num % int(t) == 0
            except:
                return False
                
        if lt == "ODD_COUNT": return s.count(t) % 2 != 0
        if lt == "EVEN_COUNT": return s.count(t) % 2 == 0
        
        return False

    def _simulate_dfa(self, dfa: DFA, s: str) -> bool:
        current_state = dfa.start_state
        for char in s:
            if current_state not in dfa.transitions: return False
            if char not in dfa.transitions[current_state]: return False 
            current_state = dfa.transitions[current_state][char]
        return current_state in dfa.accept_states