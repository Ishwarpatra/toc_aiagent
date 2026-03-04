import json
import re
import logging
import hashlib
from typing import List, Dict, Optional, Tuple, Any
import diskcache as dc

from .models import LogicSpec, DFA

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
    depth: int = 0
    in_quote: bool = False
    quote_char: Optional[str] = None
    i: int = 0
    L: int = len(expr)
    while i < L:
        ch: str = expr[i]
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


def build_starts_with_dfa(alphabet: List[str], pattern: str) -> Dict[str, Any]:
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
    
    transitions: Dict[str, Dict[str, str]] = {s: {} for s in states}
    
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


def build_substring_dfa(alphabet: List[str], pattern: str, match_at_end_only: bool = False, sink_on_full: bool = False) -> Dict[str, Any]:
    """
    Build a DFA that matches strings containing the given pattern.
    
    - match_at_end_only=True: for ENDS_WITH (only accept if pattern is at end)
    - sink_on_full=True: for NOT_CONTAINS (trap on match, for later inversion)
    - Default (both False): for CONTAINS (accept and stay accepted once pattern found)
    """
    m = len(pattern)
    
    # Build KMP failure function for efficient transitions
    pi: List[int] = [0] * m
    k: int = 0
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
    transitions: Dict[str, Dict[str, str]] = {s: {} for s in states}
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


def build_not_contains_dfa(alphabet: List[str], pattern: str) -> Dict[str, Any]:
    # build substring dfa with match sink; accept all non-sink states
    return build_substring_dfa(alphabet, pattern, sink_on_full=True)


def build_no_consecutive_dfa(alphabet: List[str], target: str) -> Dict[str, Any]:
    t = target
    states = ["q0", "q1", "sink"]
    transitions: Dict[str, Dict[str, str]] = {s: {} for s in states}
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


def build_exact_length_dfa(alphabet: List[str], n: int) -> Dict[str, Any]:
    states = [f"q{i}" for i in range(n + 2)]
    transitions: Dict[str, Dict[str, str]] = {s: {} for s in states}
    for i in range(n + 1):
        for sym in alphabet:
            if i < n:
                transitions[f"q{i}"][sym] = f"q{i+1}"
            else:
                transitions[f"q{n}"][sym] = f"q{n+1}"
    for sym in alphabet:
        transitions[f"q{n+1}"][sym] = f"q{n+1}"
    return {"states": states, "alphabet": alphabet, "start_state": "q0", "accept_states": [f"q{n}"], "transitions": transitions}


def build_min_length_dfa(alphabet: List[str], n: int) -> Dict[str, Any]:
    states = [f"q{i}" for i in range(n + 1)]
    transitions: Dict[str, Dict[str, str]] = {s: {} for s in states}
    for i in range(n):
        for sym in alphabet:
            transitions[f"q{i}"][sym] = f"q{i+1}"
    for sym in alphabet:
        transitions[f"q{n}"][sym] = f"q{n}"
    return {"states": states, "alphabet": alphabet, "start_state": "q0", "accept_states": [f"q{n}"], "transitions": transitions}


def build_max_length_dfa(alphabet: List[str], n: int) -> Dict[str, Any]:
    states = [f"q{i}" for i in range(n + 2)]
    transitions: Dict[str, Dict[str, str]] = {s: {} for s in states}
    for i in range(n):
        for sym in alphabet:
            transitions[f"q{i}"][sym] = f"q{i+1}"
    for sym in alphabet:
        transitions[f"q{n}"][sym] = f"q{n+1}"
        transitions[f"q{n+1}"][sym] = f"q{n+1}"
    return {"states": states, "alphabet": alphabet, "start_state": "q0", "accept_states": [f"q{i}" for i in range(n + 1)], "transitions": transitions}


def build_length_mod_k_dfa(alphabet: List[str], k: int, r: int = 0) -> Dict[str, Any]:
    states = [f"q{i}" for i in range(k)]
    transitions: Dict[str, Dict[str, str]] = {s: {} for s in states}
    for i in range(k):
        for sym in alphabet:
            transitions[f"q{i}"][sym] = f"q{(i + 1) % k}"
    return {"states": states, "alphabet": alphabet, "start_state": "q0", "accept_states": [f"q{r % k}"], "transitions": transitions}


def build_count_mod_k_dfa(alphabet: List[str], target_symbol: str, k: int, r: int = 0) -> Dict[str, Any]:
    states = [f"q{i}" for i in range(k)]
    transitions: Dict[str, Dict[str, str]] = {s: {} for s in states}
    for i in range(k):
        for sym in alphabet:
            transitions[f"q{i}"][sym] = f"q{(i + (1 if sym == target_symbol else 0)) % k}"
    return {"states": states, "alphabet": alphabet, "start_state": "q0", "accept_states": [f"q{r % k}"], "transitions": transitions}


def build_min_count_dfa(alphabet: List[str], target_symbol: str, min_count: int) -> Dict[str, Any]:
    """
    Build a DFA that accepts strings with at least min_count occurrences of target_symbol.
    Uses states to track the count up to min_count, then stays in accepting state.
    """
    if min_count <= 0:
        # If min count is 0 or less, accept all strings
        states = ["q_accept"]
        transitions = {"q_accept": {sym: "q_accept" for sym in alphabet}}
        return {
            "states": states,
            "alphabet": alphabet,
            "start_state": "q_accept",
            "accept_states": ["q_accept"],
            "transitions": transitions
        }

    # States: q0 (0 matches), q1 (1 match), ..., qN (N matches and beyond)
    states = [f"q{i}" for i in range(min_count + 1)]
    transitions: Dict[str, Dict[str, str]] = {s: {} for s in states}

    # For each state, define transitions
    for i in range(min_count + 1):
        for sym in alphabet:
            if sym == target_symbol:
                # If we match the target symbol
                if i < min_count:
                    # Move to next count state
                    transitions[f"q{i}"][sym] = f"q{i+1}"
                else:
                    # Stay in the final state (have enough matches)
                    transitions[f"q{i}"][sym] = f"q{min_count}"
            else:
                # If we don't match the target symbol
                if i < min_count:
                    # Stay in current state
                    transitions[f"q{i}"][sym] = f"q{i}"
                else:
                    # Stay in final state
                    transitions[f"q{i}"][sym] = f"q{min_count}"

    # Accept states: all states from min_count onwards
    accept_states = [f"q{i}" for i in range(min_count, min_count + 1)]

    return {
        "states": states,
        "alphabet": alphabet,
        "start_state": "q0",
        "accept_states": accept_states,
        "transitions": transitions
    }


def build_max_count_dfa(alphabet: List[str], target_symbol: str, max_count: int) -> Dict[str, Any]:
    """
    Build a DFA that accepts strings with at most max_count occurrences of target_symbol.
    Uses states to track the count up to max_count, then goes to rejecting sink.
    """
    # States: q0 (0 matches), q1 (1 match), ..., qN (N matches), q_over (too many)
    states = [f"q{i}" for i in range(max_count + 1)] + ["q_over"]
    transitions: Dict[str, Dict[str, str]] = {s: {} for s in states}

    # For each counting state, define transitions
    for i in range(max_count + 1):
        for sym in alphabet:
            if sym == target_symbol:
                # If we match the target symbol
                if i < max_count:
                    # Move to next count state
                    transitions[f"q{i}"][sym] = f"q{i+1}"
                else:
                    # Too many matches, go to rejecting state
                    transitions[f"q{i}"][sym] = "q_over"
            else:
                # If we don't match the target symbol
                if i <= max_count:
                    # Stay in current state
                    transitions[f"q{i}"][sym] = f"q{i}"

    # Transition from overflow state
    for sym in alphabet:
        transitions["q_over"][sym] = "q_over"

    # Accept states: all states up to max_count
    accept_states = [f"q{i}" for i in range(max_count + 1)]

    return {
        "states": states,
        "alphabet": alphabet,
        "start_state": "q0",
        "accept_states": accept_states,
        "transitions": transitions
    }


def build_divisible_by_dfa(alphabet: List[str], k: int) -> Dict[str, Any]:
    """
    Build a DFA that accepts strings representing numbers divisible by k.
    This function is now base-agnostic and works with any ordered alphabet.
    """
    # Determine base and mapping based on the alphabet
    base = len(alphabet)
    mapping = {sym: idx for idx, sym in enumerate(alphabet)}

    # Validate that all symbols in alphabet are single characters for numeric interpretation
    if not all(len(sym) == 1 for sym in alphabet):
        raise ValueError("DIVISIBLE_BY: all alphabet symbols must be single characters for numeric interpretation")

    states = [f"r{r}" for r in range(k)]
    transitions: Dict[str, Dict[str, str]] = {s: {} for s in states}
    for r in range(k):
        for sym in alphabet:
            d = mapping.get(sym, 0)
            new_r = (r * base + d) % k
            transitions[f"r{r}"][sym] = f"r{new_r}"
    return {"states": states, "alphabet": alphabet, "start_state": "r0", "accept_states": ["r0"], "transitions": transitions}


def build_product_even_dfa(alphabet: List[str]) -> Dict[str, Any]:
    """
    Build a DFA that accepts strings where the product of all symbols is even.
    In numeric contexts, this means at least one even digit is present.
    """
    even_symbols = set()
    for s in alphabet:
        # Check if symbol represents an even number
        try:
            if s.isdigit() and int(s) % 2 == 0:
                even_symbols.add(s)
            elif len(s) == 1 and ord(s) % 2 == 0:  # For non-digit symbols, use ASCII value
                even_symbols.add(s)
        except ValueError:
            # If not a digit, skip for even check
            continue

    states = ['q0', 'q1']
    transitions: Dict[str, Dict[str, str]] = {s: {} for s in states}
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

        # Check for range queries first (special case)
        range_match = re.search(r"(\w+)\s+of\s+(\w+)\s+between\s+(\d+)\s+and\s+(\d+)", lower)
        if range_match:
            quantifier, target, low, high = range_match.groups()
            if quantifier in ["count", "number"]:
                # This is a range query: "count of X between A and B"
                # Interpret as: count(X) >= A AND count(X) <= B
                low_int, high_int = int(low), int(high)

                # Create two atomic specs: count >= low AND count <= high
                spec1 = LogicSpec(logic_type="MIN_COUNT", target=f"{target}:{low_int}", alphabet=["0", "1"])
                spec2 = LogicSpec(logic_type="MAX_COUNT", target=f"{target}:{high_int}", alphabet=["0", "1"])

                child_dicts = [spec1.model_dump(), spec2.model_dump()]
                composite = {"logic_type": "AND", "target": None, "children": child_dicts}
                spec = LogicSpec(**composite)
                unify_alphabets_for_spec(spec)
                return spec

        # Check for standard composite operations
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

        child_dicts: List[Dict[str, Any]] = [c.model_dump() if hasattr(c, "model_dump") else c.__dict__ for c in child_specs]
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
        # Initialize persistent cache with concurrency-safe settings
        import os
        # CRITICAL: Use absolute path to avoid issues with multiprocessing spawn
        cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.cache'))
        os.makedirs(cache_dir, exist_ok=True)
        # CRITICAL: diskcache with WAL mode for concurrent read/write access
        # timeout=60: Wait up to 60 seconds for lock acquisition
        # sqlite_journal_mode="wal": Enable Write-Ahead Logging
        # sqlite_synchronous=1 (NORMAL): Good balance of safety and performance
        self.cache = dc.Cache(
            directory=cache_dir,
            timeout=60,
            sqlite_journal_mode="wal",
            sqlite_synchronous=1,
        )
        # CRITICAL: Track cache hit/miss statistics for telemetry
        self.cache_hits = 0
        self.cache_misses = 0

        # product_engine and repair_engine are expected to be available in your repo
        # If you have ProductConstructionEngine import it; here we assume product_engine has combine/invert
        try:
            from .product import ProductConstructionEngine
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

    def _get_atomic_spec_hash(self, logic_type: str, target: str, alphabet_tuple: tuple) -> str:
        """
        Generate a hash for atomic operation parameters.
        """
        import hashlib
        params_tuple = (logic_type, target, alphabet_tuple)
        return hashlib.md5(str(params_tuple).encode()).hexdigest()

    def _get_cached_atomic_dfa(self, logic_type: str, target: str, alphabet_tuple: tuple) -> Optional[tuple]:
        """
        Retrieve cached atomic DFA from persistent cache.
        Tracks hit/miss statistics for telemetry.
        Uses JSON serialization for reliable disk storage.
        """
        import json
        cache_key = self._get_atomic_spec_hash(logic_type, target, alphabet_tuple)
        try:
            raw_data = self.cache.get(cache_key)
            if raw_data is None:
                self.cache_misses += 1
                import structlog
                log = structlog.get_logger()
                log.info("cache_get_result", logic_type=logic_type, target=target[:30], cache_key=cache_key[:16], result_type=None, result_is_none=True, cache_hits=self.cache_hits, cache_misses=self.cache_misses)
                return None
            
            # Deserialize JSON string back to tuple
            dfa_dict = json.loads(raw_data)
            result = tuple(dfa_dict.items())
            
            # CRITICAL: Track cache hit/miss for telemetry rollup
            self.cache_hits += 1
            
            import structlog
            log = structlog.get_logger()
            log.info("cache_get_result", logic_type=logic_type, target=target[:30], cache_key=cache_key[:16], result_type="tuple", result_is_none=False, cache_hits=self.cache_hits, cache_misses=self.cache_misses)
            return result
        except Exception as e:
            import structlog
            log = structlog.get_logger()
            log.warning("cache_get_failed", logic_type=logic_type, target=target[:30], error=str(e))
            self.cache_misses += 1
            return None

    def _set_cached_atomic_dfa(self, logic_type: str, target: str, alphabet_tuple: tuple, dfa_tuple: tuple) -> None:
        """
        Store atomic DFA in persistent cache.
        Uses JSON serialization for reliable disk storage.
        CRITICAL: Raises RuntimeError on cache write failure to expose serialization issues.
        """
        import json
        cache_key = self._get_atomic_spec_hash(logic_type, target, alphabet_tuple)
        try:
            # CRITICAL: Serialize to JSON string for reliable disk storage
            dfa_dict = dict(dfa_tuple)
            json_data = json.dumps(dfa_dict)
            result = self.cache.set(cache_key, json_data, expire=3600*24*30)
            
            import structlog
            log = structlog.get_logger()
            log.info("cache_write_success", logic_type=logic_type, target=target[:30], cache_key=cache_key[:16], result=result)
        except Exception as e:
            # CRITICAL: Raise RuntimeError to expose cache serialization failures
            raise RuntimeError(f"CACHE WRITE FAILED for {logic_type}({target[:30]}): {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring and debugging.
        Returns hit/miss counts and total cached entries.
        """
        try:
            # diskcache doesn't have direct hit/miss tracking like lru_cache
            # but we can get total entries and size
            total_entries = len(self.cache)
            total_size = self.cache.volume()
            return {
                "total_entries": total_entries,
                "total_size_bytes": total_size,
                "cache_directory": self.cache.directory,
            }
        except Exception as e:
            return {
                "error": str(e),
                "total_entries": 0,
                "total_size_bytes": 0,
            }

    def _build_atomic_dfa(self, logic_type: str, target: str, alphabet: List[str]) -> Optional[tuple]:
        """
        Build atomic DFA and cache it persistently.
        """
        t = target or ""

        try:
            if logic_type == "STARTS_WITH":
                d = build_starts_with_dfa(alphabet, t)
                return tuple(d.items())  # Convert dict to hashable tuple
            if logic_type == "CONTAINS":
                d = build_substring_dfa(alphabet, t)
                return tuple(d.items())
            if logic_type == "ENDS_WITH":
                d = build_substring_dfa(alphabet, t, match_at_end_only=True)
                return tuple(d.items())
            if logic_type == "NO_CONSECUTIVE":
                d = build_no_consecutive_dfa(alphabet, t)
                return tuple(d.items())
            if logic_type == "EXACT_LENGTH":
                d = build_exact_length_dfa(alphabet, int(t))
                return tuple(d.items())
            if logic_type == "MIN_LENGTH":
                d = build_min_length_dfa(alphabet, int(t))
                return tuple(d.items())
            if logic_type == "MAX_LENGTH":
                d = build_max_length_dfa(alphabet, int(t))
                return tuple(d.items())
            if logic_type == "LENGTH_MOD":
                r_str, k_str = t.split(":")
                k = int(k_str); r = int(r_str)
                d = build_length_mod_k_dfa(alphabet, k, r)
                return tuple(d.items())
            if logic_type == "COUNT_MOD":
                # t expected "symbol:r:k"
                sym, r_str, k_str = t.split(":")
                d = build_count_mod_k_dfa(alphabet, sym, int(k_str), int(r_str))
                return tuple(d.items())
            if logic_type == "DIVISIBLE_BY":
                d = build_divisible_by_dfa(alphabet, int(t))
                return tuple(d.items())
            if logic_type == "PRODUCT_EVEN":
                d = build_product_even_dfa(alphabet)
                return tuple(d.items())

            # Parity counting: EVEN_COUNT / ODD_COUNT
            if logic_type in ["EVEN_COUNT", "ODD_COUNT"]:
                # Use count_mod_k with k=2, r=0 for EVEN, r=1 for ODD
                r = 0 if logic_type == "EVEN_COUNT" else 1
                t_val = t or "1"  # Default target if not provided
                d = build_count_mod_k_dfa(alphabet, t_val, k=2, r=r)
                return tuple(d.items())

            # Count-based operations: MIN_COUNT and MAX_COUNT
            if logic_type == "MIN_COUNT":
                # t expected "symbol:count"
                if ":" in t:
                    symbol, count_str = t.split(":")
                    count = int(count_str)
                    d = build_min_count_dfa(alphabet, symbol, count)
                    return tuple(d.items())
            if logic_type == "MAX_COUNT":
                # t expected "symbol:count"
                if ":" in t:
                    symbol, count_str = t.split(":")
                    count = int(count_str)
                    d = build_max_count_dfa(alphabet, symbol, count)
                    return tuple(d.items())

            # NOT operations that have their own builders
            if logic_type == "NOT_STARTS_WITH":
                starts_dfa_dict = build_starts_with_dfa(alphabet, t)
                starts_dfa = DFA(**starts_dfa_dict)
                inverted_dfa = self.product_engine.invert(starts_dfa)
                return tuple(inverted_dfa.model_dump().items())
            if logic_type == "NOT_ENDS_WITH":
                ends_dfa_dict = build_substring_dfa(alphabet, t, match_at_end_only=True)
                ends_dfa = DFA(**ends_dfa_dict)
                inverted_dfa = self.product_engine.invert(ends_dfa)
                return tuple(inverted_dfa.model_dump().items())
            if logic_type == "NOT_CONTAINS":
                contains_dfa_dict = build_substring_dfa(alphabet, t)
                contains_dfa = DFA(**contains_dfa_dict)
                inverted_dfa = self.product_engine.invert(contains_dfa)
                return tuple(inverted_dfa.model_dump().items())

        except Exception as e:
            logger.warning(f"[Architect] Atomic builder failed for {logic_type} {t}: {e}")
            # Return a default rejecting DFA as tuple
            states = ("q0",)
            alphabet_tuple = tuple(alphabet)
            transitions = (("q0", {sym: "q0" for sym in alphabet}),)
            start_state = "q0"
            accept_states = ()
            return ("states", states), ("alphabet", alphabet_tuple), ("transitions", transitions), ("start_state", start_state), ("accept_states", accept_states)

        # CRITICAL: Strict else block - never silently return None
        # A caching layer must never return None on cache miss for unsupported keys
        raise ValueError(f"Unsupported atomic logic type for cache: {logic_type} (target: {t})")


    def design(self, spec: LogicSpec) -> DFA:
        """
        Design a DFA from a LogicSpec. Handles composite (AND/OR/NOT) and atomic specs.
        Uses persistent diskcache to avoid recomputing the same atomic DFA multiple times.

        CRITICAL: For composite operations, the unified alphabet is propagated DOWN
        to all children BEFORE building them. This prevents alphabet mismatch errors.
        """
        import structlog
        log = structlog.get_logger()
        
        # For atomic operations, try to use the persistent cache
        if not spec.children and spec.logic_type not in ["AND", "OR", "NOT"]:  # Atomic operation
            # Convert to hashable types for caching
            alphabet_tuple = tuple(sorted(spec.alphabet)) if spec.alphabet else ('0', '1')
            
            log.info("design_atomic", logic_type=spec.logic_type, target=(spec.target or "")[:30], alphabet=spec.alphabet, has_children=bool(spec.children))
            
            # Try cache first
            cached_result = self._get_cached_atomic_dfa(spec.logic_type, spec.target or "", alphabet_tuple)
            if cached_result is not None:
                # Cache hit
                log.info("cache_hit", logic_type=spec.logic_type, target=(spec.target or "")[:30])
                result_dict = dict(cached_result)
                return DFA(**result_dict)
            
            # Cache miss - build and store
            log.info("cache_miss", logic_type=spec.logic_type, target=(spec.target or "")[:30])
            try:
                result_tuple = self._build_atomic_dfa(spec.logic_type, spec.target or "", list(alphabet_tuple))
                if result_tuple is not None:
                    # Store in cache
                    self._set_cached_atomic_dfa(spec.logic_type, spec.target or "", alphabet_tuple, result_tuple)
                    result_dict = dict(result_tuple)
                    return DFA(**result_dict)
                else:
                    log.warning("build_atomic returned None", logic_type=spec.logic_type)
            except Exception as e:
                logger.info(f"[Architect] Atomic build failed for {spec.logic_type}, computing normally: {e}")
                # If build fails, continue with normal computation
        else:
            log.info("design_composite_or_has_children", logic_type=spec.logic_type, has_children=bool(spec.children))

        # Composite handling (unchanged from original)
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

        # Atomic cases: build deterministic DFAs for common types (non-cached fallback)
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
                # Build CONTAINS DFA then invert via product engine (includes complete_dfa)
                contains_dfa_dict = build_substring_dfa(a, t)
                contains_dfa = DFA(**contains_dfa_dict)
                return self.product_engine.invert(contains_dfa)
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

            # NOT_STARTS_WITH: build STARTS_WITH then invert via product engine
            if lt == "NOT_STARTS_WITH":
                starts_dfa_dict = build_starts_with_dfa(a, t)
                starts_dfa = DFA(**starts_dfa_dict)
                # Use product engine invert which includes complete_dfa()
                return self.product_engine.invert(starts_dfa)

            # NOT_ENDS_WITH: build ENDS_WITH then invert via product engine
            if lt == "NOT_ENDS_WITH":
                ends_dfa_dict = build_substring_dfa(a, t, match_at_end_only=True)
                ends_dfa = DFA(**ends_dfa_dict)
                # Use product engine invert which includes complete_dfa()
                return self.product_engine.invert(ends_dfa)

            # Count-based operations: MIN_COUNT and MAX_COUNT
            if lt == "MIN_COUNT":
                # t expected "symbol:count"
                if ":" in t:
                    symbol, count_str = t.split(":")
                    count = int(count_str)
                    # Build a DFA that counts occurrences of the symbol
                    d = build_min_count_dfa(a, symbol, count)
                    return DFA(**d)
            if lt == "MAX_COUNT":
                # t expected "symbol:count"
                if ":" in t:
                    symbol, count_str = t.split(":")
                    count = int(count_str)
                    # Build a DFA that counts occurrences of the symbol
                    d = build_max_count_dfa(a, symbol, count)
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