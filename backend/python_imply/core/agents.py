import json
import re
import logging
from typing import List, Dict, Optional, Tuple

from core.models import LogicSpec, DFA

logger = logging.getLogger(__name__)


class BaseAgent:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def call_ollama(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """
        Placeholder for LLM call. Returns None in environments where LLM is not set up.
        In your deployment replace this with actual Ollama/LLM call.
        """
        logger.debug("[BaseAgent] call_ollama stub called.")
        return None


# --- Small parsing and utility helpers (used by AnalystAgent) ---


def split_top_level(expr: str, sep: str) -> List[str]:
    """
    Split expr by sep at top-level while ignoring separators inside quotes or parentheses.
    """
    parts = []
    buf = []
    depth = 0
    in_quote = False
    quote_char = None
    i = 0
    L = len(expr)
    while i < L:
        ch = expr[i]
        if ch in ('"', "'"):
            if in_quote and ch == quote_char:
                in_quote = False
                quote_char = None
            elif not in_quote:
                in_quote = True
                quote_char = ch
            buf.append(ch)
            i += 1
            continue
        if not in_quote:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth = max(0, depth - 1)
            # check sep
            if depth == 0 and expr[i:i + len(sep)].lower() == sep:
                parts.append(''.join(buf).strip())
                buf = []
                i += len(sep)
                continue
        buf.append(ch)
        i += 1
    if buf:
        parts.append(''.join(buf).strip())
    return [p for p in parts if p]


def unify_alphabets_for_spec(spec: LogicSpec) -> List[str]:
    """
    Recursively unify alphabets from children and set spec.alphabet.
    Returns unified alphabet list.
    """
    if not getattr(spec, "children", None):
        if getattr(spec, "alphabet", None):
            return spec.alphabet
        return ['0', '1']
    merged = []
    for child in spec.children:
        child_alpha = unify_alphabets_for_spec(child)
        for s in child_alpha:
            if s not in merged:
                merged.append(s)
    # basic policy: if merged is length 1 and single-letter, assume pair (single, paired)
    if len(merged) == 1:
        single = merged[0]
        pair = 'b' if single.isalpha() else '1'
        merged = [single, pair]
    # attach to spec
    spec.alphabet = merged
    # add a reasoning note if union ambiguous
    if hasattr(spec, "reasoning"):
        spec.reasoning = (spec.reasoning or "") + f" [Alphabet unified to {merged}]"
    return merged


def flatten_children(spec: LogicSpec) -> List[LogicSpec]:
    """
    Flatten nested children of the same operator (AND/OR) to create an N-ary list.
    """
    if not getattr(spec, "children", None):
        return []
    result = []
    for child in spec.children:
        if child.logic_type == spec.logic_type and getattr(child, "children", None):
            result.extend(flatten_children(child))
        else:
            result.append(child)
    return result


def estimate_states_for_spec(spec: LogicSpec) -> int:
    """
    Heuristic estimator of states required for atomic specs.
    Used for product-size pre-checks (upper bound estimation).
    """
    lt = getattr(spec, "logic_type", "")
    t = getattr(spec, "target", "")
    if lt in ("AND", "OR"):
        total = 1
        for c in spec.children:
            total *= max(1, estimate_states_for_spec(c))
            if total > 1_000_000:
                return total
        return total
    if lt == "NOT":
        return max(2, estimate_states_for_spec(spec.children[0]) if spec.children else 2)
    if lt in ("STARTS_WITH", "ENDS_WITH", "CONTAINS"):
        return (len(t) + 1) if t else 3
    if lt == "NO_CONSECUTIVE":
        return 3
    if lt == "DIVISIBLE_BY":
        try:
            return max(2, int(t))
        except:
            return 10
    if lt in ("LENGTH_MOD",):
        try:
            k = int(t.split(":")[-1])
            return max(2, k)
        except:
            return 10
    if lt == "COUNT_MOD":
        try:
            k = int(t.split(":")[-1])
            return max(2, k)
        except:
            return 10
    if lt == "PRODUCT_EVEN":
        return 2
    if lt in ("EVEN_COUNT", "ODD_COUNT"):
        return 2
    return 10


# --- DFA builders for atomic specs (these return dicts convertible to DFA model) ---


def build_starts_with_dfa(alphabet: List[str], pattern: str) -> Dict:
    """
    Build a DFA that accepts strings starting with the given pattern.
    
    States: q0, q1, ..., q{len(pattern)} (accept), and q_dead (reject sink)
    - On matching the prefix, we reach the accept state and stay there.
    - On mismatch before reaching accept, we go to dead state.
    """
    n = len(pattern)
    
    # States: q0 to q{n} for matching progress, plus q_dead for rejection
    states = [f"q{i}" for i in range(n + 1)] + ["q_dead"]
    start = "q0"
    accept_state = f"q{n}"
    accept = [accept_state]
    
    transitions = {s: {} for s in states}
    
    # Transitions for matching states (q0 to q{n-1})
    for i in range(n):
        current = f"q{i}"
        for sym in alphabet:
            if sym == pattern[i]:
                # Match: advance to next state
                transitions[current][sym] = f"q{i+1}"
            else:
                # Mismatch: go to dead state permanently
                transitions[current][sym] = "q_dead"
    
    # Accept state: once we've matched the prefix, any symbol keeps us accepting
    for sym in alphabet:
        transitions[accept_state][sym] = accept_state
    
    # Dead state: sink - all transitions loop back
    for sym in alphabet:
        transitions["q_dead"][sym] = "q_dead"
    
    return {
        "states": states, 
        "alphabet": alphabet, 
        "start_state": start, 
        "accept_states": accept, 
        "transitions": transitions
    }


def build_substring_dfa(alphabet: List[str], pattern: str, match_at_end_only: bool = False, sink_on_full: bool = False) -> Dict:
    """
    Build a DFA that matches strings containing the given pattern.
    
    - match_at_end_only=True: for ENDS_WITH (only accept if pattern is at end)
    - sink_on_full=True: for NOT_CONTAINS (trap on match, for later inversion)
    - Default (both False): for CONTAINS (accept and stay accepted once pattern found)
    """
    m = len(pattern)
    
    # Build KMP failure function for efficient transitions
    pi = [0] * m
    k = 0
    for i in range(1, m):
        while k > 0 and pattern[k] != pattern[i]:
            k = pi[k - 1]
        if pattern[k] == pattern[i]:
            k += 1
        pi[i] = k

    def next_len(j: int, c: str) -> int:
        """Compute next state given current prefix length j and input symbol c."""
        while j > 0 and (j >= m or pattern[j] != c):
            j = pi[j - 1]
        if j < m and pattern[j] == c:
            return j + 1
        return j

    # Determine states needed
    if sink_on_full:
        # For NOT_CONTAINS: q0..q{m-1} (matching), q{m} (matched=sink=reject)
        total_states = m + 1
    else:
        # q0..q{m} where q{m} is accept
        total_states = m + 1
    
    states = [f"q{i}" for i in range(total_states)]
    transitions = {s: {} for s in states}
    accept_state = f"q{m}"
    
    # Build transitions
    for j in range(total_states):
        name = f"q{j}"
        for sym in alphabet:
            if j == m:
                # We're at the "pattern matched" state
                if match_at_end_only:
                    # For ENDS_WITH: after matching, if more input comes,
                    # we need KMP-like fallback to handle overlapping matches
                    ns = next_len(j, sym)
                    transitions[name][sym] = f"q{ns}"
                else:
                    # For CONTAINS / NOT_CONTAINS with sink_on_full:
                    # Once matched, stay in this state (trap)
                    transitions[name][sym] = name
            else:
                ns = next_len(j, sym)
                transitions[name][sym] = f"q{ns}"
    
    # Determine accept states
    if match_at_end_only:
        # ENDS_WITH: only accept when we've matched the pattern AND are at end
        accept_states = [accept_state]
    elif sink_on_full:
        # NOT_CONTAINS: accept all EXCEPT match state (caller will invert)
        # Actually for not_contains, we accept states where pattern NOT matched
        accept_states = [f"q{i}" for i in range(m)]  # q0..q{m-1}
    else:
        # CONTAINS: accept once pattern is found (q{m} and stay there)
        accept_states = [accept_state]
    
    return {
        "states": states,
        "alphabet": alphabet,
        "start_state": "q0",
        "accept_states": accept_states,
        "transitions": transitions
    }


def build_not_contains_dfa(alphabet: List[str], pattern: str) -> Dict:
    # build substring dfa with match sink; accept all non-sink states
    return build_substring_dfa(alphabet, pattern, sink_on_full=True)


def build_no_consecutive_dfa(alphabet: List[str], target: str) -> Dict:
    t = target
    states = ["q0", "q1", "sink"]
    transitions = {s: {} for s in states}
    for sym in alphabet:
        if sym == t:
            transitions["q0"][sym] = "q1"
            transitions["q1"][sym] = "sink"
            transitions["sink"][sym] = "sink"
        else:
            transitions["q0"][sym] = "q0"
            transitions["q1"][sym] = "q0"
            transitions["sink"][sym] = "sink"
    return {"states": states, "alphabet": alphabet, "start_state": "q0", "accept_states": ["q0", "q1"], "transitions": transitions}


def build_exact_length_dfa(alphabet: List[str], n: int) -> Dict:
    states = [f"q{i}" for i in range(n + 2)]
    transitions = {s: {} for s in states}
    for i in range(n + 1):
        for sym in alphabet:
            if i < n:
                transitions[f"q{i}"][sym] = f"q{i+1}"
            else:
                transitions[f"q{n}"][sym] = f"q{n+1}"
    for sym in alphabet:
        transitions[f"q{n+1}"][sym] = f"q{n+1}"
    return {"states": states, "alphabet": alphabet, "start_state": "q0", "accept_states": [f"q{n}"], "transitions": transitions}


def build_min_length_dfa(alphabet: List[str], n: int) -> Dict:
    states = [f"q{i}" for i in range(n + 1)]
    transitions = {s: {} for s in states}
    for i in range(n):
        for sym in alphabet:
            transitions[f"q{i}"][sym] = f"q{i+1}"
    for sym in alphabet:
        transitions[f"q{n}"][sym] = f"q{n}"
    return {"states": states, "alphabet": alphabet, "start_state": "q0", "accept_states": [f"q{n}"], "transitions": transitions}


def build_max_length_dfa(alphabet: List[str], n: int) -> Dict:
    states = [f"q{i}" for i in range(n + 2)]
    transitions = {s: {} for s in states}
    for i in range(n):
        for sym in alphabet:
            transitions[f"q{i}"][sym] = f"q{i+1}"
    for sym in alphabet:
        transitions[f"q{n}"][sym] = f"q{n+1}"
        transitions[f"q{n+1}"][sym] = f"q{n+1}"
    return {"states": states, "alphabet": alphabet, "start_state": "q0", "accept_states": [f"q{i}" for i in range(n + 1)], "transitions": transitions}


def build_length_mod_k_dfa(alphabet: List[str], k: int, r: int = 0) -> Dict:
    states = [f"q{i}" for i in range(k)]
    transitions = {s: {} for s in states}
    for i in range(k):
        for sym in alphabet:
            transitions[f"q{i}"][sym] = f"q{(i + 1) % k}"
    return {"states": states, "alphabet": alphabet, "start_state": "q0", "accept_states": [f"q{r % k}"], "transitions": transitions}


def build_count_mod_k_dfa(alphabet: List[str], target_symbol: str, k: int, r: int = 0) -> Dict:
    states = [f"q{i}" for i in range(k)]
    transitions = {s: {} for s in states}
    for i in range(k):
        for sym in alphabet:
            transitions[f"q{i}"][sym] = f"q{(i + (1 if sym == target_symbol else 0)) % k}"
    return {"states": states, "alphabet": alphabet, "start_state": "q0", "accept_states": [f"q{r % k}"], "transitions": transitions}


def build_divisible_by_dfa(alphabet: List[str], k: int) -> Dict:
    # Determine base and mapping
    base = None
    mapping = {}
    if set(alphabet) == set(['0', '1']):
        base = 2
        mapping = {c: int(c) for c in alphabet}
    elif len(alphabet) == 2 and all(len(sym) == 1 for sym in alphabet):
        base = 2
        mapping = {alphabet[0]: 0, alphabet[1]: 1}
    elif all(sym.isdigit() and len(sym) == 1 for sym in alphabet):
        base = 10
        mapping = {sym: int(sym) for sym in alphabet}
    else:
        raise ValueError("DIVISIBLE_BY: unsupported alphabet for numeric interpretation")

    states = [f"r{r}" for r in range(k)]
    transitions = {s: {} for s in states}
    for r in range(k):
        for sym in alphabet:
            d = mapping.get(sym, 0)
            new_r = (r * base + d) % k
            transitions[f"r{r}"][sym] = f"r{new_r}"
    return {"states": states, "alphabet": alphabet, "start_state": "r0", "accept_states": ["r0"], "transitions": transitions}


def build_product_even_dfa(alphabet: List[str]) -> Dict:
    even_symbols = set()
    if set(alphabet) == set(['0', '1']):
        even_symbols = {'0'}
    elif len(alphabet) == 2 and all(len(sym) == 1 for sym in alphabet):
        even_symbols = {alphabet[0]}
    else:
        for s in alphabet:
            if s.isdigit() and int(s) % 2 == 0:
                even_symbols.add(s)
    states = ['q0', 'q1']
    transitions = {s: {} for s in states}
    for sym in alphabet:
        transitions['q0'][sym] = 'q1' if sym in even_symbols else 'q0'
        transitions['q1'][sym] = 'q1'
    return {"states": states, "alphabet": alphabet, "start_state": "q0", "accept_states": ['q1'], "transitions": transitions}


# --- AnalystAgent: tries local fast composite parse before falling back to LLM ---


class AnalystAgent(BaseAgent):
    def __init__(self, model_name: str):
        super().__init__(model_name)

    def try_local_composite_parse(self, user_prompt: str) -> Optional[LogicSpec]:
        lp = user_prompt.strip()
        lower = lp.lower()
        op = None
        sep = None
        if " and " in lower:
            op = "AND"; sep = " and "
        elif " or " in lower:
            op = "OR"; sep = " or "
        else:
            return None

        parts = split_top_level(lp, sep)
        if len(parts) < 2:
            return None

        child_specs = []
        for part in parts:
            atomic = LogicSpec.from_prompt(part)
            if atomic:
                child_specs.append(atomic)
                continue
            # Try recursive (this may call LLM) but be conservative
            nested = None
            try:
                nested = self.analyze(part)
            except Exception:
                nested = None
            if nested:
                child_specs.append(nested)
            else:
                return None

        child_dicts = [c.model_dump() if hasattr(c, "model_dump") else c.__dict__ for c in child_specs]
        composite = {"logic_type": op, "target": None, "children": child_dicts}
        spec = LogicSpec(**composite)
        unify_alphabets_for_spec(spec)
        return spec

    def analyze(self, user_prompt: str) -> LogicSpec:
        print(f"\n[Agent 1] Analyzing Request: '{user_prompt}'")
        # Fast local parse attempt
        try:
            local_spec = self.try_local_composite_parse(user_prompt)
            if local_spec:
                print(f"   -> [Local Parse] Composite {local_spec.logic_type} parsed with {len(local_spec.children)} children")
                return local_spec
        except Exception as e:
            print(f"   -> [Local Parse] failed: {e}")

        # Heuristic atomic
        heuristic = LogicSpec.from_prompt(user_prompt)
        if heuristic:
            print(f"   -> Detected Atomic (heuristic): {heuristic.logic_type}")
            return heuristic

        # Fallback to LLM (if available)
        system_prompt = "You are a Logic Specialist. Output a JSON LogicSpec object with fields: logic_type, target, children (list)."
        resp = self.call_ollama(system_prompt, user_prompt)
        if resp:
            try:
                cleaned = resp.replace("```json", "").replace("```", "").strip()
                data = json.loads(cleaned)
                # Normalize keys if needed
                if "type" in data and "logic_type" not in data:
                    data["logic_type"] = data.pop("type")
                if "constraints" in data and "children" not in data:
                    data["children"] = data.pop("constraints")
                spec = LogicSpec(**data)
                unify_alphabets_for_spec(spec)
                return spec
            except Exception as e:
                logger.warning(f"[Analyst] LLM parse failed: {e}")

        # Absolute default
        print("   -> [Default] Falling back to default LogicSpec CONTAINS '1'")
        return LogicSpec(logic_type="CONTAINS", target="1", alphabet=["0", "1"])


# --- ArchitectAgent: builds DFAs, supports N-ary combine with size checks ---


class ArchitectAgent(BaseAgent):
    def __init__(self, model_name: str, max_product_states: int = 2000):
        super().__init__(model_name)
        self.max_product_states = max_product_states
        # product_engine and repair_engine are expected to be available in your repo
        # If you have ProductConstructionEngine import it; here we assume product_engine has combine/invert
        try:
            from core.product import ProductConstructionEngine
            self.product_engine = ProductConstructionEngine()
        except Exception:
            # Define a minimal placeholder that raises if used
            class _PE:
                def combine(self, a, b, op): raise NotImplementedError("Product engine not available")
                def invert(self, a): raise NotImplementedError("Product engine not available")
            self.product_engine = _PE()

    def _propagate_alphabet_down(self, spec: LogicSpec, alphabet: List[str]) -> None:
        """
        Recursively propagate a unified alphabet DOWN to all children.
        This ensures all partial DFAs use the same symbol set, preventing
        alphabet mismatch crashes in ProductConstructionEngine.
        """
        spec.alphabet = alphabet
        if hasattr(spec, 'children') and spec.children:
            for child in spec.children:
                self._propagate_alphabet_down(child, alphabet)

    def design(self, spec: LogicSpec) -> DFA:
        """
        Design a DFA from a LogicSpec. Handles composite (AND/OR/NOT) and atomic specs.
        
        CRITICAL: For composite operations, the unified alphabet is propagated DOWN
        to all children BEFORE building them. This prevents alphabet mismatch errors.
        """
        # Composite handling
        if spec.logic_type == "NOT":
            if not spec.children:
                raise ValueError("'NOT' node missing children")
            
            # CRITICAL: Propagate parent's alphabet to child before building
            full_alphabet = spec.alphabet or ['0', '1']
            self._propagate_alphabet_down(spec.children[0], full_alphabet)
            
            child_dfa = self.design(spec.children[0])
            return self.product_engine.invert(child_dfa)

        if spec.logic_type in ["AND", "OR"]:
            # CRITICAL FIX: Propagate unified alphabet DOWN to all children FIRST
            # This ensures all partial DFAs speak the same language (e.g., {a, b, 0, 1})
            full_alphabet = spec.alphabet or ['0', '1']
            
            # Force all direct children to inherit the unified alphabet
            for child in spec.children:
                self._propagate_alphabet_down(child, full_alphabet)
            
            # Flatten children (LogicSpec objects)
            flat = flatten_children(spec)
            if not flat:
                flat = spec.children
            
            # Re-apply alphabet to flattened children (in case flattening pulled in new children)
            for c in flat:
                self._propagate_alphabet_down(c, full_alphabet)
            
            # Estimate growth
            estimated = 1
            for c in flat:
                estimated *= max(1, estimate_states_for_spec(c))
                if estimated > self.max_product_states:
                    raise ValueError(f"Product size estimate too large: {estimated} states (threshold={self.max_product_states})")
            
            # Build DFAs for children
            child_dfas = []
            for c in flat:
                dfa = self.design(c)
                child_dfas.append((c, dfa))
            
            # Sort by size to combine small first (optimization)
            child_dfas.sort(key=lambda pair: len(pair[1].states))
            current = child_dfas[0][1]
            
            for _, nxt in child_dfas[1:]:
                inter_est = len(current.states) * len(nxt.states)
                if inter_est > self.max_product_states:
                    raise ValueError(f"Intermediate product would exceed safe size ({inter_est} > {self.max_product_states}).")
                current = self.product_engine.combine(current, nxt, spec.logic_type)
            
            return current

        # Atomic cases: build deterministic DFAs for common types
        lt = spec.logic_type
        a = spec.alphabet or ['0', '1']
        t = spec.target or ""

        try:
            if lt == "STARTS_WITH":
                d = build_starts_with_dfa(a, t)
                return DFA(**d)
            if lt == "CONTAINS":
                d = build_substring_dfa(a, t)
                return DFA(**d)
            if lt == "ENDS_WITH":
                d = build_substring_dfa(a, t, match_at_end_only=True)
                return DFA(**d)
            if lt == "NOT_CONTAINS":
                d = build_not_contains_dfa(a, t)
                return DFA(**d)
            if lt == "NO_CONSECUTIVE":
                d = build_no_consecutive_dfa(a, t)
                return DFA(**d)
            if lt == "EXACT_LENGTH":
                d = build_exact_length_dfa(a, int(t))
                return DFA(**d)
            if lt == "MIN_LENGTH":
                d = build_min_length_dfa(a, int(t))
                return DFA(**d)
            if lt == "MAX_LENGTH":
                d = build_max_length_dfa(a, int(t))
                return DFA(**d)
            if lt == "LENGTH_MOD":
                r_str, k_str = t.split(":")
                k = int(k_str); r = int(r_str)
                d = build_length_mod_k_dfa(a, k, r)
                return DFA(**d)
            if lt == "COUNT_MOD":
                # t expected "symbol:r:k"
                sym, r_str, k_str = t.split(":")
                d = build_count_mod_k_dfa(a, sym, int(k_str), int(r_str))
                return DFA(**d)
            if lt == "DIVISIBLE_BY":
                d = build_divisible_by_dfa(a, int(t))
                return DFA(**d)
            if lt == "PRODUCT_EVEN":
                d = build_product_even_dfa(a)
                return DFA(**d)
            
            # Parity counting: EVEN_COUNT / ODD_COUNT
            if lt in ["EVEN_COUNT", "ODD_COUNT"]:
                # Use count_mod_k with k=2, r=0 for EVEN, r=1 for ODD
                r = 0 if lt == "EVEN_COUNT" else 1
                d = build_count_mod_k_dfa(a, t, k=2, r=r)
                return DFA(**d)
            
            # NOT_STARTS_WITH: invert the STARTS_WITH DFA
            if lt == "NOT_STARTS_WITH":
                starts_dfa_dict = build_starts_with_dfa(a, t)
                # Invert accept states
                all_states = starts_dfa_dict["states"]
                accept_states = starts_dfa_dict["accept_states"]
                inverted_accept = [s for s in all_states if s not in accept_states]
                starts_dfa_dict["accept_states"] = inverted_accept
                return DFA(**starts_dfa_dict)
            
            # NOT_ENDS_WITH: invert the ENDS_WITH DFA
            if lt == "NOT_ENDS_WITH":
                ends_dfa_dict = build_substring_dfa(a, t, match_at_end_only=True)
                # Invert accept states
                all_states = ends_dfa_dict["states"]
                accept_states = ends_dfa_dict["accept_states"]
                inverted_accept = [s for s in all_states if s not in accept_states]
                ends_dfa_dict["accept_states"] = inverted_accept
                return DFA(**ends_dfa_dict)
        except Exception as e:
            logger.warning(f"[Architect] Atomic builder failed for {lt} {t}: {e}")

        # Fallback: ask LLM to design a DFA (existing behavior)
        system_prompt = ("You are a DFA architect. Return a JSON object describing a DFA with keys: "
                         "states, start_state, accept_states, transitions. Do NOT include commentary.")
        resp = self.call_ollama(system_prompt, f"Design DFA for: {spec.logic_type} {spec.target or ''}")
        if resp:
            try:
                cleaned = resp.replace("```json", "").replace("```", "").strip()
                data = json.loads(cleaned)
                return DFA(**data)
            except Exception as e:
                logger.warning(f"[Architect] LLM DFA parse failed: {e}")

        # As a last resort, return a trivial rejecting DFA
        states = ["q0"]
        return DFA(states=states, alphabet=a, transitions={"q0": {sym: "q0" for sym in a}}, start_state="q0", accept_states=[])