import logging
from typing import Tuple, List, Dict

from .models import DFA, LogicSpec

logger = logging.getLogger(__name__)


class DeterministicValidator:
    def __init__(self):
        pass

    def validate(self, dfa: DFA, spec: LogicSpec) -> Tuple[bool, str]:
        """
        Simulate DFA on a set of generated test strings derived from spec and return (is_valid, message).
        """
        # Generate some test inputs
        test_alphabet = dfa.alphabet if getattr(dfa, "alphabet", None) else ['0', '1']
        test_inputs = ["", test_alphabet[0], test_alphabet[-1], test_alphabet[0] + test_alphabet[-1], test_alphabet[-1] * 2]
        if spec.target:
            t = spec.target
            if len(t) < 10:
                test_inputs.extend([t, t + test_alphabet[0], test_alphabet[0] + t])

        test_inputs = sorted(list(set(test_inputs)))
        error_log = []

        for s in test_inputs:
            if any(c not in dfa.alphabet for c in s):
                continue

            expected = self.get_truth(s, spec, debug=False)
            # simulate DFA
            curr = dfa.start_state
            crashed = False
            for char in s:
                if curr not in dfa.transitions or char not in dfa.transitions[curr]:
                    crashed = True
                    break
                curr = dfa.transitions[curr][char]
            actual = (curr in dfa.accept_states) and not crashed

            if expected != actual:
                error_log.append(f"FAIL: '{s}' -> Got {actual}, Expected {expected}")

        if not error_log:
            return True, "Passed"
        return False, "\n".join(error_log[:5])

    def get_truth(self, s: str, spec: LogicSpec, debug: bool = False) -> bool:
        lt = spec.logic_type.strip().upper()
        t = spec.target
        result = False

        # Recursive
        if lt == "AND":
            return self.get_truth(s, spec.children[0], debug) and self.get_truth(s, spec.children[1], debug)
        if lt == "OR":
            return self.get_truth(s, spec.children[0], debug) or self.get_truth(s, spec.children[1], debug)
        if lt == "NOT":
            return not self.get_truth(s, spec.children[0], debug)

        # Atomic
        if lt == "STARTS_WITH":
            result = s.startswith(t)
        elif lt == "NOT_STARTS_WITH":
            result = not s.startswith(t)
        elif lt == "ENDS_WITH":
            result = s.endswith(t)
        elif lt == "NOT_ENDS_WITH":
            result = not s.endswith(t)
        elif lt == "CONTAINS":
            result = t in s
        elif lt == "NOT_CONTAINS":
            result = t not in s
        elif lt == "NO_CONSECUTIVE":
            result = (t * 2) not in s
        elif lt == "DIVISIBLE_BY":
            try:
                t_int = int(t)
                # determine mapping
                alpha = spec.alphabet
                if set(alpha) == set(['0', '1']):
                    val_s = s
                    base = 2
                elif len(alpha) == 2 and all(len(sym) == 1 for sym in alpha):
                    translation = {alpha[0]: '0', alpha[1]: '1'}
                    val_s = ''.join(translation.get(ch, '0') for ch in s)
                    base = 2
                elif all(sym.isdigit() and len(sym) == 1 for sym in alpha):
                    val_s = s
                    base = 10
                else:
                    if debug:
                        logger.debug("DIVISIBLE_BY: unsupported alphabet for numeric interpretation")
                    return False
                # parse as int with base 2 or 10
                if base == 2:
                    num = int(val_s, 2) if val_s else 0
                else:
                    num = int(val_s) if val_s else 0
                result = (num % t_int == 0)
            except Exception:
                result = False
        elif lt == "NOT_DIVISIBLE_BY":
            try:
                result = not self.get_truth(s, LogicSpec(logic_type="DIVISIBLE_BY", target=t, alphabet=spec.alphabet))
            except Exception:
                result = False
        elif lt == "EVEN_NUMBER":
            try:
                result = self.get_truth(s, LogicSpec(logic_type="DIVISIBLE_BY", target="2", alphabet=spec.alphabet))
            except Exception:
                result = False
        elif lt == "EXACT_LENGTH":
            try:
                n = int(t)
                result = len(s) == n
            except:
                result = False
        elif lt == "MIN_LENGTH":
            try:
                n = int(t); result = len(s) >= n
            except:
                result = False
        elif lt == "MAX_LENGTH":
            try:
                n = int(t); result = len(s) <= n
            except:
                result = False
        elif lt == "LENGTH_MOD":
            try:
                r_str, k_str = t.split(":")
                r, k = int(r_str), int(k_str)
                result = (len(s) % k == r % k)
            except:
                result = False
        elif lt == "COUNT_MOD":
            # Accept both "symbol:r:k" and "symbol:k:r" encodings to be permissive.
            try:
                parts = t.split(":")
                if len(parts) == 3:
                    sym, r_str, k_str = parts
                    r, k = int(r_str), int(k_str)
                    if (s.count(sym) % k) == (r % k):
                        result = True
                    else:
                        sym2, k_str2, r_str2 = parts
                        k2, r2 = int(k_str2), int(r_str2)
                        result = (s.count(sym2) % k2) == (r2 % k2)
                else:
                    result = False
            except Exception:
                result = False
        elif lt == "PRODUCT_EVEN":
            try:
                alpha = spec.alphabet
                if set(alpha) == set(['0', '1']):
                    even_symbols = {'0'}
                elif len(alpha) == 2 and all(len(sym) == 1 for sym in alpha):
                    even_symbols = {alpha[0]}
                else:
                    even_symbols = {sym for sym in alpha if sym.isdigit() and int(sym) % 2 == 0}
                result = any(ch in even_symbols for ch in s)
            except Exception:
                result = False
        elif lt == "ODD_COUNT":
            try:
                result = s.count(t) % 2 != 0
            except:
                result = False
        elif lt == "EVEN_COUNT":
            try:
                result = s.count(t) % 2 == 0
            except:
                result = False
        else:
            logger.debug(f"Unknown logic type: {lt}")
            result = False

        if debug:
            logger.debug(f"Eval: {lt} ('{t}') on '{s}' -> {result}")
        return result