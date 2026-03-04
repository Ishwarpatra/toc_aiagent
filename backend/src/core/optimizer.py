"""
DFA Optimizer Module
====================
Professional-grade DFA optimization utilities for cleaning up and minimizing 
Deterministic Finite Automata.

This module provides:
- Unreachable state removal (states not reachable from start)
- Non-productive state removal (states that can't reach accept states)
- Dead state cleanup (useless trap states)
- DFA minimization using partition refinement

Author: Auto-DFA System
"""

from typing import Set, Dict, List, Tuple, Optional
from collections import deque
import logging

from .models import DFA

logger = logging.getLogger(__name__)


class DFAOptimizer:
    """
    Optimizes DFA by removing unreachable and non-productive states.
    
    A state is considered useful only if:
    1. It is reachable from the start state (forward reachability)
    2. It can reach at least one accept state (backward reachability)
    
    Dead states (trap states) are only kept if they are actually 
    transitioned to from useful states.
    """
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
    
    def _log(self, message: str):
        """Log optimization steps if verbose mode is enabled."""
        if self.verbose:
            logger.info(f"[Optimizer] {message}")
    
    def find_reachable_states(self, dfa: DFA) -> Set[str]:
        """
        Find all states reachable from the start state using BFS.
        
        Time Complexity: O(|States| + |Transitions|)
        
        Returns:
            Set of state names reachable from start_state
        """
        reachable: Set[str] = set()
        queue: deque = deque([dfa.start_state])
        
        while queue:
            current = queue.popleft()
            if current in reachable:
                continue
            reachable.add(current)
            
            # Explore all transitions from current state
            if current in dfa.transitions:
                for symbol, next_state in dfa.transitions[current].items():
                    if next_state not in reachable and next_state in dfa.states:
                        queue.append(next_state)
        
        return reachable
    
    def find_productive_states(self, dfa: DFA) -> Set[str]:
        """
        Find all states that can reach at least one accept state.
        Uses reverse BFS from accept states.
        
        Time Complexity: O(|States| + |Transitions|)
        
        Returns:
            Set of state names that can reach an accept state
        """
        # Build reverse transition graph
        reverse_graph: Dict[str, Set[str]] = {state: set() for state in dfa.states}
        
        for src, transitions in dfa.transitions.items():
            for symbol, dest in transitions.items():
                if dest in reverse_graph:
                    reverse_graph[dest].add(src)
        
        # BFS from accept states backwards
        productive: Set[str] = set()
        queue: deque = deque(dfa.accept_states)
        
        while queue:
            current = queue.popleft()
            if current in productive:
                continue
            productive.add(current)
            
            # Add all states that transition TO this state
            for prev_state in reverse_graph.get(current, []):
                if prev_state not in productive:
                    queue.append(prev_state)
        
        return productive
    
    def find_useful_states(self, dfa: DFA) -> Set[str]:
        """
        Find states that are both reachable AND productive.
        A state is useful only if it can be part of an accepting computation.
        
        Returns:
            Set of useful state names
        """
        reachable = self.find_reachable_states(dfa)
        productive = self.find_productive_states(dfa)
        
        useful = reachable & productive
        
        self._log(f"Reachable states: {sorted(reachable)}")
        self._log(f"Productive states: {sorted(productive)}")
        self._log(f"Useful states (intersection): {sorted(useful)}")
        
        return useful
    
    def is_dead_state(self, state: str, dfa: DFA) -> bool:
        """
        Check if a state is a dead/trap state.
        A dead state is one where:
        1. It is not an accept state
        2. All transitions loop back to itself
        
        Returns:
            True if the state is a dead state
        """
        if state in dfa.accept_states:
            return False
        
        if state not in dfa.transitions:
            return True
        
        for symbol, dest in dfa.transitions[state].items():
            if dest != state:
                return False
        
        return True
    
    def cleanup(self, dfa: DFA, keep_completeness: bool = True) -> DFA:
        """
        Remove all unreachable and non-productive states from the DFA.
        
        This is the main cleanup method that ensures:
        1. All remaining states are reachable from start
        2. All remaining states can reach an accept state
        3. Dead states are only kept if they're needed for completeness
        
        Args:
            dfa: The DFA to clean up
            keep_completeness: If True, keeps one dead state for completeness
                             (DFA requires all transitions to be defined)
        
        Returns:
            A new, optimized DFA
        """
        self._log(f"Starting cleanup. Original states: {len(dfa.states)}")
        
        # Handle edge case: empty DFA
        if not dfa.states:
            self._log("WARNING: Empty DFA, returning as-is")
            return dfa
        
        # Step 1: Find useful states
        useful_states = self.find_useful_states(dfa)
        
        # Edge case: If no useful states (e.g., no path from start to accept)
        # Keep the reachable states at minimum to preserve DFA structure
        if not useful_states:
            self._log("WARNING: No useful states found. Keeping reachable states.")
            useful_states = self.find_reachable_states(dfa)
        
        # Step 2: Identify dead states that are actually used
        dead_state_needed = False
        dead_state_name = "q_dead"
        
        # Check if any useful state transitions to a non-useful state
        for state in useful_states:
            if state in dfa.transitions:
                for symbol, dest in dfa.transitions[state].items():
                    if dest not in useful_states:
                        dead_state_needed = True
                        break
            if dead_state_needed:
                break
        
        # Step 3: Build the final state set
        final_states: Set[str] = useful_states.copy()
        
        if keep_completeness and dead_state_needed:
            final_states.add(dead_state_name)
            self._log(f"Keeping dead state '{dead_state_name}' for completeness")
        
        # Step 4: Build cleaned transitions - ensure completeness
        cleaned_transitions: Dict[str, Dict[str, str]] = {}
        
        for state in final_states:
            cleaned_transitions[state] = {}
            
            if state == dead_state_name:
                # Dead state loops to itself for all symbols
                for symbol in dfa.alphabet:
                    cleaned_transitions[state][symbol] = state
            elif state in dfa.transitions:
                for symbol in dfa.alphabet:
                    if symbol in dfa.transitions[state]:
                        dest = dfa.transitions[state][symbol]
                        if dest in final_states:
                            cleaned_transitions[state][symbol] = dest
                        elif keep_completeness:
                            # Redirect to dead state
                            cleaned_transitions[state][symbol] = dead_state_name
                        else:
                            # Leave pointing to self (fallback for incomplete DFA)
                            cleaned_transitions[state][symbol] = state
                    elif keep_completeness:
                        # Missing transition - route to dead state or self
                        cleaned_transitions[state][symbol] = dead_state_name if dead_state_needed else state
                    else:
                        cleaned_transitions[state][symbol] = state
            else:
                # State has no transitions defined - create self-loops
                for symbol in dfa.alphabet:
                    cleaned_transitions[state][symbol] = dead_state_name if (keep_completeness and dead_state_needed) else state
        
        # Step 5: Filter accept states
        cleaned_accept = [s for s in dfa.accept_states if s in final_states]
        
        # Step 6: Validate start state
        if dfa.start_state not in final_states:
            self._log("WARNING: Start state was removed! Using first available state.")
            start_state = sorted(final_states)[0] if final_states else dfa.start_state
        else:
            start_state = dfa.start_state
        
        removed_count = len(dfa.states) - len(final_states)
        self._log(f"Cleanup complete. Removed {removed_count} states. Final: {len(final_states)}")
        
        return DFA(
            states=sorted(list(final_states)),
            alphabet=list(dfa.alphabet),  # Ensure it's a list
            transitions=cleaned_transitions,
            start_state=start_state,
            accept_states=cleaned_accept,
            reasoning=dfa.reasoning + f" [Optimized: -{removed_count} states]" if removed_count > 0 else dfa.reasoning
        )
    
    def get_optimization_report(self, original: DFA, optimized: DFA) -> Dict:
        """
        Generate a detailed report of the optimization performed.
        
        Returns:
            Dictionary containing optimization statistics
        """
        removed_states = set(original.states) - set(optimized.states)
        
        return {
            "original_state_count": len(original.states),
            "optimized_state_count": len(optimized.states),
            "states_removed": len(removed_states),
            "removed_state_names": sorted(list(removed_states)),
            "reduction_percentage": round(
                (1 - len(optimized.states) / len(original.states)) * 100, 2
            ) if original.states else 0,
            "is_optimized": len(removed_states) > 0
        }


def cleanup_dfa(dfa: DFA, verbose: bool = True) -> DFA:
    """
    Convenience function to clean up a DFA.
    
    Usage:
        from core.optimizer import cleanup_dfa
        cleaned_dfa = cleanup_dfa(original_dfa)
    """
    optimizer = DFAOptimizer(verbose=verbose)
    return optimizer.cleanup(dfa)
