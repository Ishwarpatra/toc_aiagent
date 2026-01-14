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
    states = [f"q{i}" for i in range(len(pattern) + 1)]
    start = "q0"
    accept = [f"q{len(pattern)}"]
    transitions = {s: {} for s in states}
    for i in range(len(pattern) + 1):
        for sym in alphabet:
            if i < len(pattern) and sym == pattern[i]:
                transitions[f"q{i}"][sym] = f"q{i+1}"
            else:
                transitions[f"q{i}"][sym] = "q0"
    return {"states": states, "alphabet": alphabet, "start_state": start, "accept_states": accept, "transitions": transitions}


def build_substring_dfa(alphabet: List[str], pattern: str, match_at_end_only: bool = False, sink_on_full: bool = False) -> Dict:
    m = len(pattern)
    states = [f"q{i}" for i in range(m + (1 if sink_on_full else 0) + 1)]
    # Use a simple KMP-like next-state behaviour (conservative)
    transitions = {}
    pi = [0] * m
    k = 0
    for i in range(1, m):
        while k > 0 and pattern[k] != pattern[i]:
            k = pi[k - 1]
        if pattern[k] == pattern[i]:
            k += 1
        pi[i] = k

    def next_len(j: int, c: str):
        while j > 0 and (j >= m or pattern[j] != c):
            j = pi[j - 1]
        if j < m and pattern[j] == c:
            return j + 1
        return j

    total_states = m + 1 if not sink_on_full else m + 1 + 1
    for j in range(total_states):
        name = f"q{j}"
        transitions[name] = {}
        for sym in alphabet:
            if sink_on_full and j == m + 1:
                transitions[name][sym] = name
                continue
            cur = j if j <= m else m
            ns = next_len(cur, sym)
            if ns == m:
                if sink_on_full:
                    transitions[name][sym] = f"q{m+1}"
                else:
                    transitions[name][sym] = f"q{m}"
            else:
                transitions[name][sym] = f"q{ns}"
    if match_at_end_only:
        accept_states = [f"q{m}"]
    else:
        if sink_on_full:
            accept_states = [f"q{i}" for i in range(m + 1)]
            # but in sink_on_full design, we will treat q{m+1} as rejecting sink for NOT_CONTAINS
            accept_states = [f"q{i}" for i in range(m + 1)]
        else:
            accept_states = [f"q{m}"]
    return {"states": [f"q{i}" for i in range(total_states)], "alphabet": alphabet, "start_state": "q0", "accept_states": accept_states, "transitions": transitions}


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

    def design(self, spec: LogicSpec) -> DFA:
        # Composite handling
        if spec.logic_type == "NOT":
            if not spec.children:
                raise ValueError("'NOT' node missing children")
            child_dfa = self.design(spec.children[0])
            return self.product_engine.invert(child_dfa)

        if spec.logic_type in ["AND", "OR"]:
            # Flatten children
            flat = flatten_children(spec)
            if not flat:
                flat = spec.children
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
            # Sort by size to combine small first
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