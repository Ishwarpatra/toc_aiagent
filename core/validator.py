from typing import List
from .models import DFA, LogicSpec
class DeterministicValidator:
    def validate(self, dfa: DFA, spec: LogicSpec) -> tuple[bool, str]:
        """
        Runs the DFA against the truth function.
        """
        print(f"\n[Validator] Running Checks for {spec.logic_type} '{spec.target}'...")
        
        test_inputs = ["", "0", "1", "00", "01", "10", "11"]
        if spec.target:
            t = spec.target
            test_inputs.extend([t, t+"0", "0"+t, "1"+t+"0"])
            if len(t) > 1: test_inputs.append(t[:-1])
            if spec.logic_type in ["DIVISIBLE_BY", "ODD_COUNT", "EVEN_COUNT"]:
                test_inputs.extend(["000", "111", "1010", "0101", "1100", "0011"])
        
        test_inputs = sorted(list(set(test_inputs)))
        error_log = []

        for s in test_inputs:
            if any(c not in dfa.alphabet for c in s): continue
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
        t = spec.target
        lt = spec.logic_type
        
        if lt == "STARTS_WITH": return s.startswith(t)
        if lt == "NOT_STARTS_WITH": return not s.startswith(t)
        if lt == "ENDS_WITH": return s.endswith(t)
        if lt == "NOT_ENDS_WITH": return not s.endswith(t)
        if lt == "CONTAINS": return t in s
        if lt == "NOT_CONTAINS": return t not in s
        if lt == "NO_CONSECUTIVE": return t*2 not in s 
        
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