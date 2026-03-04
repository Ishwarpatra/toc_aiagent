from typing import List, Dict
from .models import DFA

class ProductConstructionEngine:
    def minimize(self, dfa: DFA) -> DFA:
        """
        Minimal Myhill-Nerode-like DFA minimization.
        Merges equivalent states to simplify the machine.
        """
        if not dfa.states: return dfa
        
        # 1. Remove unreachable states
        reachable = {dfa.start_state}
        queue = [dfa.start_state]
        while queue:
            s = queue.pop(0)
            for char in dfa.alphabet:
                nxt = dfa.transitions.get(s, {}).get(char)
                if nxt and nxt not in reachable:
                    reachable.add(nxt)
                    queue.append(nxt)
        
        relevant_states = sorted(list(reachable))
        
        # 2. Initial partitions: Accept vs Reject
        accept_set = set(dfa.accept_states) & reachable
        reject_set = set(relevant_states) - accept_set
        
        partitions = []
        if accept_set: partitions.append(tuple(sorted(list(accept_set))))
        if reject_set: partitions.append(tuple(sorted(list(reject_set))))
        
        def get_partition_idx(state):
            for i, p in enumerate(partitions):
                if state in p: return i
            return -1

        # 3. Refine partitions
        changed = True
        while changed:
            changed = False
            new_partitions = []
            for p in partitions:
                if len(p) <= 1:
                    new_partitions.append(p)
                    continue
                
                # Group states in this partition by their transition behaviors
                split = {}
                for s in p:
                    # Key is the tuple of (partition_index_of_next_state) for each char
                    behavior = []
                    for char in dfa.alphabet:
                        nxt = dfa.transitions.get(s, {}).get(char)
                        behavior.append(get_partition_idx(nxt) if nxt else -1)
                    behavior_key = tuple(behavior)
                    if behavior_key not in split: split[behavior_key] = []
                    split[behavior_key].append(s)
                
                if len(split) > 1:
                    changed = True
                    for group in split.values():
                        new_partitions.append(tuple(sorted(group)))
                else:
                    new_partitions.append(p)
            partitions = new_partitions

        # 4. Reconstruct minimized DFA
        state_map = {} # old_state -> new_representative
        new_states = []
        new_accept_states = []
        new_start_state = ""
        
        for i, p in enumerate(partitions):
            rep = p[0]
            # Rename representative if it's a "dead" sink
            is_dead = True
            if rep in accept_set:
                is_dead = False
            else:
                for char in dfa.alphabet:
                    nxt = dfa.transitions.get(rep, {}).get(char)
                    if nxt and get_partition_idx(nxt) != i:
                        is_dead = False
                        break
            
            new_name = "dead" if is_dead and len(partitions) > 1 else f"s{i}"
            # Preserve original start state name if it's the only one in partition
            if dfa.start_state in p:
                if dfa.start_state.startswith("q"):
                   new_name = dfa.start_state # Try to keep q0 if possible
                new_start_state = new_name
            
            new_states.append(new_name)
            if rep in accept_set:
                new_accept_states.append(new_name)
            
            for s in p:
                state_map[s] = new_name

        new_transitions = {s: {} for s in new_states}
        for i, p in enumerate(partitions):
            rep = p[0]
            curr_new = state_map[rep]
            for char in dfa.alphabet:
                old_nxt = dfa.transitions.get(rep, {}).get(char)
                if old_nxt:
                    new_transitions[curr_new][char] = state_map[old_nxt]

        return DFA(
            reasoning=dfa.reasoning + " (minimized)",
            states=sorted(new_states),
            alphabet=dfa.alphabet,
            transitions=new_transitions,
            start_state=new_start_state,
            accept_states=sorted(new_accept_states)
        )

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
        
        def get_name(s1, s2): return f"{s1}|{s2}"

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
                next1 = dfa1.transitions.get(curr1, {}).get(char, "q_dead")
                next2 = dfa2.transitions.get(curr2, {}).get(char, "q_dead")
                
                next_node = (next1, next2)
                next_name = get_name(next1, next2)
                new_transitions[curr_name][char] = next_name

                if next_node not in visited:
                    visited.add(next_node)
                    queue.append(next_node)
                    
        raw_product = DFA(
            reasoning=f"Combined ({dfa1.reasoning}) {operation} ({dfa2.reasoning})",
            states=sorted(new_states),
            alphabet=alphabet,
            transitions=new_transitions,
            start_state=get_name(dfa1.start_state, dfa2.start_state),
            accept_states=sorted(new_accept_states)
        )

        # 🟢 MINIMIZE: Clean up "useless" redundant states immediately
        return self.minimize(raw_product)

    def complete_dfa(self, dfa: DFA) -> DFA:
        """
        Make DFA fully-defined by adding a trap state for missing transitions.
        
        This is CRITICAL for inversion: if a DFA has incomplete transitions,
        inverting it (swapping accept/reject) will produce incorrect results
        because strings that would have "fallen off" the DFA are now incorrectly
        handled.
        
        Example: A DFA for "contains 'ab'" might not have transitions from
        all states for all symbols. Without completion, NOT("contains 'ab'")
        would fail to reject strings correctly.
        """
        # Check if already complete
        missing = False
        for state in dfa.states:
            for sym in dfa.alphabet:
                if sym not in dfa.transitions.get(state, {}):
                    missing = True
                    break
            if missing:
                break
        
        if not missing:
            return dfa  # Already complete
        
        # Add trap state
        trap_state = "q_trap"
        new_states = dfa.states + [trap_state] if trap_state not in dfa.states else dfa.states
        
        # Copy transitions and fill gaps
        new_transitions = {s: dict(dfa.transitions.get(s, {})) for s in dfa.states}
        new_transitions[trap_state] = {}
        
        for state in new_states:
            for sym in dfa.alphabet:
                if sym not in new_transitions.get(state, {}):
                    if state not in new_transitions:
                        new_transitions[state] = {}
                    new_transitions[state][sym] = trap_state
        
        print(f"   -> [Complete] Added trap state for {sum(1 for s in new_states for sym in dfa.alphabet if new_transitions[s][sym] == trap_state)} missing transitions")
        
        return DFA(
            reasoning=dfa.reasoning + " (completed)",
            states=sorted(new_states),
            alphabet=dfa.alphabet,
            transitions=new_transitions,
            start_state=dfa.start_state,
            accept_states=dfa.accept_states  # Trap state is NOT accepting
        )

    def invert(self, dfa: DFA) -> DFA:
        """
        Invert a DFA (NOT logic) - swap accepting and non-accepting states.
        
        CRITICAL FIX: Complete the DFA first to ensure all transitions exist.
        Otherwise, strings with missing transitions are incorrectly handled.
        """
        print(f"\n[Product Engine] Inverting DFA (NOT logic)...")
        
        # CRITICAL: Complete DFA before inversion
        completed_dfa = self.complete_dfa(dfa)
        
        new_accept_states = [s for s in completed_dfa.states if s not in completed_dfa.accept_states]
        return DFA(
            reasoning=f"NOT ({completed_dfa.reasoning})",
            states=completed_dfa.states,
            alphabet=completed_dfa.alphabet,
            transitions=completed_dfa.transitions,
            start_state=completed_dfa.start_state,
            accept_states=sorted(new_accept_states)
        )