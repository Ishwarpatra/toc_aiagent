from typing import List
from .models import DFA, LogicSpec

class DeterministicValidator:
    def validate(self, dfa: DFA, spec: LogicSpec) -> tuple[bool, str]:
        print(f"\n[Validator] Checking Logic: {spec.logic_type}")
        
        # 1. Generate Test Cases
        test_alphabet = spec.alphabet
        test_inputs = ["", "0", "1", "00", "01", "10", "11"]
        
        # Switch to letter inputs if alphabet contains a/b
        if "a" in test_alphabet or "b" in test_alphabet:
            test_inputs = ["", "a", "b", "aa", "ab", "ba", "bb", "aaa", "bbb", "bab", "aba"]

        # Add specific target cases
        if spec.target:
            t = spec.target
            test_inputs.extend([t, t + test_alphabet[0], test_alphabet[0] + t])

        test_inputs = sorted(list(set(test_inputs)))
        error_log = []

        for s in test_inputs:
            # Skip strings with invalid chars
            if any(c not in dfa.alphabet for c in s): continue

            expected = self.get_truth(s, spec)
            
            # --- SIMULATION WITH TRACE ---
            trace_path = [dfa.start_state]
            curr = dfa.start_state
            crashed = False
            crash_reason = ""
            
            for char in s:
                if curr not in dfa.transitions:
                    crashed = True; crash_reason = f"State {curr} missing transitions"; break
                if char not in dfa.transitions[curr]:
                    crashed = True; crash_reason = f"No transition for '{char}' in {curr}"; break
                curr = dfa.transitions[curr][char]
                trace_path.append(curr)
            
            actual = (curr in dfa.accept_states) and not crashed
            
            if expected != actual:
                # Failure Report
                print(f"\n   [DEBUG TRACE] Failure on input '{s}'")
                print(f"   path: {' -> '.join(trace_path)}")
                print(f"   Final State: {curr} (Accepting: {curr in dfa.accept_states})")
                print(f"   Expected: {expected} | Actual: {actual}")
                
                error_log.append(f"FAIL: '{s}' -> Got {actual}, Expected {expected}")

        if not error_log:
            print("   -> PASSED.")
            return True, "Passed"
        
        return False, "\n".join(error_log[:3])

    def get_truth(self, s: str, spec: LogicSpec) -> bool:
        # --- RECURSIVE LOGIC ---
        if spec.logic_type == "AND":
            return self.get_truth(s, spec.children[0]) and self.get_truth(s, spec.children[1])
        if spec.logic_type == "OR":
            return self.get_truth(s, spec.children[0]) or self.get_truth(s, spec.children[1])
        if spec.logic_type == "NOT":
            return not self.get_truth(s, spec.children[0])
            
        # --- ATOMIC LOGIC ---
        t = spec.target
        lt = spec.logic_type
        
        if lt == "STARTS_WITH": return s.startswith(t)
        if lt == "NOT_STARTS_WITH": return not s.startswith(t)
        
        if lt == "ENDS_WITH": return s.endswith(t)
        if lt == "NOT_ENDS_WITH": return not s.endswith(t)
        
        if lt == "CONTAINS": return t in s
        if lt == "NOT_CONTAINS": return t not in s
        
        if lt == "NO_CONSECUTIVE": return (t * 2) not in s 
        
        if lt == "DIVISIBLE_BY":
            if not s: return False 
            try:
                val_s = s.replace('a','0').replace('b','1')
                num = int(val_s, 2)
                return num % int(t) == 0
            except: return False
                
        if lt == "ODD_COUNT": return s.count(t) % 2 != 0
        if lt == "EVEN_COUNT": return s.count(t) % 2 == 0
        
        return False