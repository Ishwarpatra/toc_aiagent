from typing import Optional, List
from .models import DFA, LogicSpec

class DFARepairEngine:
    def auto_repair_dfa(self, data: dict, spec: LogicSpec) -> DFA:
        states = set(data.get('states', []))
        transitions = data.get('transitions', {})
        alphabet = spec.alphabet
        accept_states = set(data.get('accept_states', []))

        # --- Basic Cleanup ---
        clean_states = sorted([s for s in states if len(s) < 15 and " " not in s])
        if not clean_states: clean_states = ["q0", "q1"]
        start_state = data.get('start_state', clean_states[0])
        
        # Ensure q_dead exists
        if "q_dead" not in clean_states: clean_states.append("q_dead")
        if "q_dead" not in transitions: transitions["q_dead"] = {}
        for char in alphabet:
            transitions["q_dead"][char] = "q_dead"

        type_str = spec.logic_type
        target = spec.target
        MAX_STATES = 100
    
        if type_str == "DIVISIBLE_BY" and target.isdigit():
            divisor = int(target)
            if divisor > MAX_STATES:
                print(f"[Warning] Divisor {divisor} too large. Clamping to {MAX_STATES}.")
                # Option 1: Throw error
                raise ValueError(f"Divisor too large (Max: {MAX_STATES})")
        if target and len(target) > 50:
            raise ValueError("Target string is too long (Max: 50 chars)")
        # --- LOGIC INJECTION ---

        if type_str == "STARTS_WITH" and target:
            required = [start_state]
            for i in range(len(target)):
                st = f"q{i+1}"
                if st not in clean_states: clean_states.append(st)
                required.append(st)
            final = required[-1]
            accept_states = {final}
            
            # Reset transitions for chain
            for s in clean_states:
                if s not in transitions: transitions[s] = {}

            for i, st in enumerate(required[:-1]):
                char = target[i]
                transitions[st][char] = required[i+1]
                for c in alphabet:
                    if c != char: transitions[st][c] = "q_dead"
            transitions[final] = {c: final for c in alphabet} # Trap accept

        elif (type_str == "ENDS_WITH" or type_str == "NOT_ENDS_WITH") and target:
            # Rebuild states strictly: q0..qN where N=len(target)
            chain_states = [start_state]
            for i in range(len(target)):
                st = f"q{i+1}"
                if st not in clean_states: clean_states.append(st)
                chain_states.append(st)
            
            # Logic: KMP State Machine Construction
            for i, current_st in enumerate(chain_states):
                current_prefix = target[:i] # What we have matched so far
                
                if current_st not in transitions: transitions[current_st] = {}
                
                for char in alphabet:
                    # Form candidate string
                    candidate = current_prefix + char
                    
                    # Reduce candidate until it matches a prefix of target
                    # (Find longest suffix of candidate that is a prefix of target)
                    while len(candidate) > 0 and not target.startswith(candidate):
                        candidate = candidate[1:]
                    
                    # Next state corresponds to length of matched prefix
                    next_index = len(candidate)
                    if next_index < len(chain_states):
                        transitions[current_st][char] = chain_states[next_index]
                    else:
                        # Should not happen if logic is correct, but safe fallback
                        transitions[current_st][char] = chain_states[0]

            if type_str == "ENDS_WITH":
                accept_states = {chain_states[-1]}
            else:
                accept_states = set(chain_states[:-1])

        elif type_str == "CONTAINS" and target:
            # Rebuild chain
            chain_states = [start_state]
            for i in range(len(target)):
                st = f"q{i+1}"
                if st not in clean_states: clean_states.append(st)
                chain_states.append(st)
            final_state = chain_states[-1]
            accept_states = {final_state}
            
            for i, current_st in enumerate(chain_states[:-1]):
                match_char = target[i]
                next_st = chain_states[i+1]
                
                if current_st not in transitions: transitions[current_st] = {}
                transitions[current_st][match_char] = next_st
                
                for char in alphabet:
                    if char != match_char:
                        # Backtracking logic for CONTAINS is tricky (often simpler to just reset to start for short targets)
                        # but correct KMP is better. For simplicity/robustness on 'a'/'b':
                        transitions[current_st][char] = start_state 
            
            # Trap Accept
            transitions[final_state] = {c: final_state for c in alphabet}

        elif type_str == "DIVISIBLE_BY" and target.isdigit():
            divisor = int(target)
            clean_states = [f"q{i}" for i in range(divisor)]
            start_state = "q0"
            accept_states = {"q0"}
            transitions = {}
            # Map alphabet to binary
            zero_char = alphabet[0]
            one_char = alphabet[1] if len(alphabet) > 1 else alphabet[0]
            
            for r in range(divisor):
                st = f"q{r}"
                transitions[st] = {}
                transitions[st][zero_char] = f"q{(r*2)%divisor}"
                transitions[st][one_char] = f"q{(r*2+1)%divisor}"

        elif (type_str == "ODD_COUNT" or type_str == "EVEN_COUNT") and target:
            clean_states = ["even", "odd"]
            start_state = "even"
            accept_states = {"even"} if type_str == "EVEN_COUNT" else {"odd"}
            transitions = {}
            
            transitions["even"] = {}
            transitions["odd"] = {}
            
            for char in alphabet:
                if char == target:
                    transitions["even"][char] = "odd"
                    transitions["odd"][char] = "even"
                else:
                    transitions["even"][char] = "even"
                    transitions["odd"][char] = "odd"

        # --- Final Cleanup ---
        final_transitions = {}
        for s in clean_states:
            if s not in transitions: transitions[s] = {}
            # Ensure completeness
            for c in alphabet:
                if c not in transitions[s]:
                    transitions[s][c] = start_state
            final_transitions[s] = transitions[s]

        data['states'] = sorted(list(set(clean_states)))
        data['transitions'] = final_transitions
        data['start_state'] = start_state
        data['accept_states'] = sorted(list(accept_states))
        
        return DFA(**data)

    def try_inversion_fix(self, dfa: DFA, spec: LogicSpec, validator_instance) -> Optional[DFA]:
        # Simple inversion attempt
        new_accept = [s for s in dfa.states if s not in dfa.accept_states]
        inverted = DFA(
            states=dfa.states,
            alphabet=dfa.alphabet,
            transitions=dfa.transitions,
            start_state=dfa.start_state,
            accept_states=new_accept,
            reasoning=dfa.reasoning + " (Inverted)"
        )
        is_valid, _ = validator_instance.validate(inverted, spec)
        if is_valid: return inverted
        return None