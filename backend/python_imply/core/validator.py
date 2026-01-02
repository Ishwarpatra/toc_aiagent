from typing import List
from .models import DFA, LogicSpec

class DeterministicValidator:
    def validate(self, dfa: DFA, spec: LogicSpec) -> tuple[bool, str]:
        print(f"\n[Validator] Checking Logic: {spec.logic_type}")
        
        test_alphabet = spec.alphabet
        test_inputs = ["", "0", "1", "00", "01", "10", "11"]
        if "a" in test_alphabet or "b" in test_alphabet:
            test_inputs = ["", "a", "b", "aa", "ab", "ba", "bb", "aaa", "bbb", "bab", "aba"]
        if spec.target:
            t = spec.target
            test_inputs.extend([t, t + test_alphabet[0], test_alphabet[0] + t])

        test_inputs = sorted(list(set(test_inputs)))
        error_log = []

        for s in test_inputs:
            if any(c not in dfa.alphabet for c in s): continue

            # DEBUG: Only print deep trace for the problematic input
            debug_mode = (s == "bb") 
            if debug_mode: print(f"   --- Debugging Truth for '{s}' ---")
            
            expected = self.get_truth(s, spec, debug=debug_mode)
            
            # Simulation
            curr = dfa.start_state
            crashed = False
            for char in s:
                if curr not in dfa.transitions or char not in dfa.transitions[curr]:
                    crashed = True; break
                curr = dfa.transitions[curr][char]
            
            actual = (curr in dfa.accept_states) and not crashed
            
            if expected != actual:
                    print(f"   [MISMATCH] Input: '{s}' | DFA: {actual} | Truth: {expected}")
                    error_log.append(f"FAIL: '{s}' -> Got {actual}, Expected {expected}")

        if not error_log:
            print("   -> PASSED.")
            return True, "Passed"
        
        return False, "\n".join(error_log[:3])

    def get_truth(self, s: str, spec: LogicSpec, debug=False) -> bool:
        # ROBUSTNESS: Strip spaces and force upper case
        lt = spec.logic_type.strip().upper()
        t = spec.target
        
        result = False
        
        # --- RECURSIVE ---
        if lt == "AND":
            result = self.get_truth(s, spec.children[0], debug) and self.get_truth(s, spec.children[1], debug)
        elif lt == "OR":
            result = self.get_truth(s, spec.children[0], debug) or self.get_truth(s, spec.children[1], debug)
        elif lt == "NOT":
            result = not self.get_truth(s, spec.children[0], debug)
            
        # --- ATOMIC ---
        elif lt == "STARTS_WITH": result = s.startswith(t)
        elif lt == "NOT_STARTS_WITH": result = not s.startswith(t)
        elif lt == "ENDS_WITH": result = s.endswith(t)
        elif lt == "NOT_ENDS_WITH": result = not s.endswith(t)
        elif lt == "CONTAINS": result = t in s
        elif lt == "NOT_CONTAINS": result = t not in s
        elif lt == "NO_CONSECUTIVE": result = (t * 2) not in s 
        elif lt == "DIVISIBLE_BY":
            try:
                val_s = s.replace('a','0').replace('b','1')
                result = int(val_s, 2) % int(t) == 0
            except: result = False
        elif lt == "ODD_COUNT": result = s.count(t) % 2 != 0
        elif lt == "EVEN_COUNT": result = s.count(t) % 2 == 0
        else:
            if debug: print(f"      [WARNING] Unknown Logic Type: '{lt}'")
            result = False

        if debug:
            print(f"      Eval: {lt} ('{t}' if atomic) on '{s}' -> {result}")
            
        return result