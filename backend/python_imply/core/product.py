from typing import List, Dict
from .models import DFA

class ProductConstructionEngine:
    def combine(self, dfa1: DFA, dfa2: DFA, operation: str) -> DFA:
        print(f"\n[Product Engine] Combining DFAs via {operation}...")
        
        # 1. Normalize Alphabets
        if set(dfa1.alphabet) != set(dfa2.alphabet):
            raise ValueError(f"Alphabet Mismatch: {dfa1.alphabet} vs {dfa2.alphabet}")
        alphabet = sorted(dfa1.alphabet)

        # 2. Generate Product States
        new_states = []
        new_transitions = {}
        new_accept_states = []
        
        start_node = (dfa1.start_state, dfa2.start_state)
        queue = [start_node]
        visited = {start_node}
        
        def get_name(s1, s2): return f"{s1}_{s2}"

        while queue:
            curr1, curr2 = queue.pop(0)
            curr_name = get_name(curr1, curr2)
            
            if curr_name not in new_states: new_states.append(curr_name)
            
            # Determine Acceptance
            accept1 = curr1 in dfa1.accept_states
            accept2 = curr2 in dfa2.accept_states
            
            is_accept = False
            if operation == "AND": is_accept = accept1 and accept2
            elif operation == "OR": is_accept = accept1 or accept2
            
            if is_accept and curr_name not in new_accept_states:
                new_accept_states.append(curr_name)
            
            # Calculate Transitions
            new_transitions[curr_name] = {}
            for char in alphabet:
                # SAFE LOOKUP: Default to "q_dead" if transition is missing
                next1 = dfa1.transitions.get(curr1, {}).get(char, "q_dead")
                next2 = dfa2.transitions.get(curr2, {}).get(char, "q_dead")
                
                # If the child DFA uses a different name for dead state, logic still holds
                # because next1/next2 are just strings used to form the key.
                
                next_name = get_name(next1, next2)
                new_transitions[curr_name][char] = next_name

                if (next1, next2) not in visited:
                    visited.add((next1, next2))
                    queue.append((next1, next2))
        return DFA(
            reasoning=f"Combined ({dfa1.reasoning}) {operation} ({dfa2.reasoning})",
            states=sorted(new_states),
            alphabet=alphabet,
            transitions=new_transitions,
            start_state=get_name(dfa1.start_state, dfa2.start_state),
            accept_states=sorted(new_accept_states)
        )

    def invert(self, dfa: DFA) -> DFA:
        print(f"\n[Product Engine] Inverting DFA (NOT logic)...")
        new_accept_states = [s for s in dfa.states if s not in dfa.accept_states]
        return DFA(
            reasoning=f"NOT ({dfa.reasoning})",
            states=dfa.states,
            alphabet=dfa.alphabet,
            transitions=dfa.transitions,
            start_state=dfa.start_state,
            accept_states=sorted(new_accept_states)
        )