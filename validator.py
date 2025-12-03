from typing import List, Dict
from pydantic import BaseModel, Field

# --- Shared Data Models ---

class LogicSpec(BaseModel):
    logic_type: str = Field(..., description="Enum: STARTS_WITH, NOT_STARTS_WITH, ENDS_WITH, NOT_ENDS_WITH, CONTAINS, NOT_CONTAINS")
    target: str = Field(..., description="The substring required (e.g., 'aba', 'b')")
    alphabet: List[str] = Field(default=['a', 'b'])

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
        test_inputs = ["", "a", "b", "aa", "ab", "ba", "bb"]
        if spec.target:
            t = spec.target
            test_inputs.extend([t, t+"a", "a"+t, "b"+t+"a"])
            if len(t) > 1: test_inputs.append(t[:-1])
        
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
        
        if lt == "STARTS_WITH": return s.startswith(t)
        if lt == "NOT_STARTS_WITH": return not s.startswith(t)
        
        if lt == "ENDS_WITH": return s.endswith(t)
        if lt == "NOT_ENDS_WITH": return not s.endswith(t)
        
        if lt == "CONTAINS": return t in s
        if lt == "NOT_CONTAINS": return t not in s
        
        return False

    def _simulate_dfa(self, dfa: DFA, s: str) -> bool:
        current_state = dfa.start_state
        for char in s:
            current_state = dfa.transitions[current_state][char]
        return current_state in dfa.accept_states