from typing import Optional, List
from .models import DFA, LogicSpec
class DFARepairEngine:
    def auto_repair_dfa(self, data: dict, spec: LogicSpec) -> DFA:
        states = set(data.get('states', []))
        transitions = data.get('transitions', {})
        alphabet = spec.alphabet
        accept_states = set(data.get('accept_states', []))

        # Basic Cleanup
        clean_states = sorted([s for s in states if len(s) < 15 and " " not in s])
        if not clean_states: clean_states = ["q0", "q1"]
        start_state = data.get('start_state', clean_states[0])
        
        if "q_dead" not in clean_states: clean_states.append("q_dead")
        transitions["q_dead"] = {s: "q_dead" for s in alphabet}

        type_str = spec.logic_type
        target = spec.target

        # --- LOGIC INJECTION ---
        if type_str == "STARTS_WITH" and target:
            required_states = [start_state]
            for i in range(len(target)):
                st_name = f"q{i+1}"
                if st_name not in clean_states: clean_states.append(st_name)
                required_states.append(st_name)
            final_state = required_states[-1]
            accept_states = {final_state}
            for i, current_st in enumerate(required_states[:-1]):
                char_to_match = target[i]
                next_st = required_states[i+1]
                if current_st not in transitions: transitions[current_st] = {}
                transitions[current_st][char_to_match] = next_st
                for char in alphabet:
                    if char != char_to_match: transitions[current_st][char] = "q_dead"
            if final_state not in transitions: transitions[final_state] = {}
            transitions[final_state] = {s: final_state for s in alphabet}

        elif type_str == "NOT_STARTS_WITH" and target:
            chain_states = [start_state]
            for i in range(len(target)):
                st_name = f"q{i+1}"
                if st_name not in clean_states: clean_states.append(st_name)
                chain_states.append(st_name)
            safe_state = "q_safe"
            if safe_state not in clean_states: clean_states.append(safe_state)
            if safe_state not in transitions: transitions[safe_state] = {}
            transitions[safe_state] = {s: safe_state for s in alphabet}
            accept_states = set(chain_states[:-1])
            accept_states.add(safe_state)
            for i, current_st in enumerate(chain_states[:-1]):
                bad_char = target[i]
                if current_st not in transitions: transitions[current_st] = {}
                if i == len(target) - 1: transitions[current_st][bad_char] = "q_dead"
                else: transitions[current_st][bad_char] = chain_states[i+1]
                for char in alphabet:
                    if char != bad_char: transitions[current_st][char] = safe_state

        elif type_str == "CONTAINS" and target:
            chain_states = [start_state]
            for i in range(len(target)):
                st_name = f"q{i+1}"
                if st_name not in clean_states: clean_states.append(st_name)
                chain_states.append(st_name)
            final_state = chain_states[-1]
            accept_states = {final_state}
            for i, current_st in enumerate(chain_states[:-1]):
                match_char = target[i]
                next_st = chain_states[i+1]
                transitions[current_st] = {}
                transitions[current_st][match_char] = next_st
                for char in alphabet:
                    if char != match_char: transitions[current_st][char] = start_state
            if final_state not in transitions: transitions[final_state] = {}
            transitions[final_state] = {s: final_state for s in alphabet}

        elif type_str == "NOT_CONTAINS" and target:
            chain_states = [start_state]
            for i in range(len(target)):
                st_name = f"q{i+1}"
                if st_name not in clean_states: clean_states.append(st_name)
                chain_states.append(st_name)
            final_state = chain_states[-1]
            accept_states = set(chain_states[:-1]) 
            for i, current_st in enumerate(chain_states[:-1]):
                match_char = target[i]
                next_st = chain_states[i+1]
                transitions[current_st] = {}
                transitions[current_st][match_char] = next_st
                for char in alphabet:
                    if char != match_char: transitions[current_st][char] = start_state
            if final_state not in transitions: transitions[final_state] = {}
            transitions[final_state] = {s: final_state for s in alphabet}

        elif (type_str == "ENDS_WITH" or type_str == "NOT_ENDS_WITH") and target:
            chain_states = [start_state]
            for i in range(len(target)):
                st_name = f"q{i+1}"
                if st_name not in clean_states: clean_states.append(st_name)
                chain_states.append(st_name)
            for i, current_st in enumerate(chain_states):
                current_prefix = target[:i]
                if current_st not in transitions: transitions[current_st] = {}
                for char in alphabet:
                    candidate = current_prefix + char
                    while len(candidate) > 0 and not target.startswith(candidate):
                        candidate = candidate[1:]
                    next_index = len(candidate)
                    if next_index < len(chain_states):
                        next_st_name = chain_states[next_index]
                        transitions[current_st][char] = next_st_name
            if type_str == "ENDS_WITH": accept_states = {chain_states[-1]}
            else: accept_states = set(chain_states[:-1])

        elif type_str == "DIVISIBLE_BY" and target.isdigit():
            divisor = int(target)
            clean_states = [f"q{i}" for i in range(divisor)]
            start_state = "q_start"
            clean_states.append(start_state)
            transitions = {}
            for r in range(divisor):
                state_name = f"q{r}"
                transitions[state_name] = {}
                transitions[state_name]['0'] = f"q{(r * 2) % divisor}"
                transitions[state_name]['1'] = f"q{(r * 2 + 1) % divisor}"
            transitions[start_state] = transitions["q0"].copy()
            accept_states = {"q0"}

        elif type_str == "NO_CONSECUTIVE" and target:
            clean_states = ["safe", "seen_one", "trap"]
            start_state = "safe"
            accept_states = {"safe", "seen_one"}
            transitions = {}
            bad_char = target
            other_char = '1' if bad_char == '0' else '0'
            transitions["safe"] = {other_char: "safe", bad_char: "seen_one"}
            transitions["seen_one"] = {other_char: "safe", bad_char: "trap"}
            transitions["trap"] = {s: "trap" for s in alphabet}

        elif (type_str == "EVEN_COUNT" or type_str == "ODD_COUNT") and target:
            clean_states = ["even", "odd"]
            start_state = "even"
            accept_states = {"even"} if type_str == "EVEN_COUNT" else {"odd"}
            transitions = {}
            count_char = target
            other_char = '1' if count_char == '0' else '0'
            transitions["even"] = {other_char: "even", count_char: "odd"}
            transitions["odd"] = {other_char: "odd", count_char: "even"}

        # Fallback Cleanup
        for state in clean_states:
            if state not in transitions: transitions[state] = {}
            for symbol in alphabet:
                if symbol not in transitions[state]:
                    transitions[state][symbol] = start_state

        # Prune Unreachable
        reachable = {start_state}
        queue = [start_state]
        while queue:
            curr = queue.pop(0)
            if curr in transitions:
                for next_st in transitions[curr].values():
                    if next_st not in reachable:
                        reachable.add(next_st)
                        queue.append(next_st)
        
        clean_states = [s for s in clean_states if s in reachable]
        final_accept = [s for s in accept_states if s in reachable]
        
        final_transitions = {}
        for s in clean_states:
            if s in transitions:
                final_transitions[s] = transitions[s]

        data['states'] = sorted(clean_states)
        data['transitions'] = final_transitions
        data['start_state'] = start_state
        data['accept_states'] = sorted(final_accept)
        return DFA(**data)

    def try_inversion_fix(self, dfa: DFA, spec: LogicSpec, validator_instance) -> Optional[DFA]:
        all_states = set(dfa.states)
        current_accept = set(dfa.accept_states)
        new_accept = list(all_states - current_accept)
        inverted_dfa = DFA(
            states=dfa.states,
            alphabet=dfa.alphabet,
            transitions=dfa.transitions,
            start_state=dfa.start_state,
            accept_states=new_accept,
            reasoning=dfa.reasoning + " (Auto-Inverted by System)"
        )
        
        # Parity Logic Bypass
        if spec.logic_type in ["ODD_COUNT", "EVEN_COUNT"]:
            test_inputs = ["", spec.target, spec.target*2, spec.target*3]
            for inp in test_inputs:
                expected = self._validate_parity_logic(spec.logic_type, spec.target, inp)
                curr = inverted_dfa.start_state
                for char in inp:
                    curr = inverted_dfa.transitions.get(curr, {}).get(char, "q_dead")
                if (curr in inverted_dfa.accept_states) != expected:
                    return None
            return inverted_dfa

        is_valid, _ = validator_instance.validate(inverted_dfa, spec)
        if is_valid: return inverted_dfa
        return None

    def _validate_parity_logic(self, logic_type, target, test_str):
        count = test_str.count(target)
        if logic_type == "ODD_COUNT": return count % 2 != 0
        elif logic_type == "EVEN_COUNT": return count % 2 == 0
        return False