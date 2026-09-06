"""
Grammar Engine for Deterministic Finite Automata (DFA).

Provides algorithms to convert a DFA into its corresponding Right-Linear
Regular Grammar based on formal language theory theorems.
"""

from typing import Dict, List
import string
from .models import DFA


class GrammarBuilder:
    """
    Mathematical engine to convert a DFA into a Right-Linear Regular Grammar.
    
    Theorem:
      For a DFA M = (Q, Σ, δ, q0, F):
      1. Non-terminals V correspond to states in Q.
         The start state q0 is assigned the start variable S.
      2. Terminals correspond to the alphabet Σ.
      3. For every transition δ(qi, a) = qj, add production:
            Vi -> aVj
      4. For every accept state qk in F, add production:
            Vk -> ε (represented as empty string "")
    """

    @staticmethod
    def build_from_dfa(dfa: DFA) -> Dict[str, List[str]]:
        """
        Convert a DFA instance to a Right-Linear Regular Grammar mapping.
        
        Args:
            dfa: A validated DFA object.
            
        Returns:
            Dict[str, List[str]]: Mapping from variable name (e.g., 'S', 'A')
                                  to a list of RHS production strings.
        """
        # Map start state to 'S'
        state_to_var: Dict[str, str] = {dfa.start_state: "S"}

        # Available uppercase letters excluding 'S'
        available_vars = [c for c in string.ascii_uppercase if c != "S"]

        # Sort remaining states for deterministic variable naming
        sorted_states = sorted([s for s in dfa.states if s != dfa.start_state])
        var_idx = 0
        for state in sorted_states:
            if var_idx < len(available_vars):
                state_to_var[state] = available_vars[var_idx]
            else:
                state_to_var[state] = f"V{var_idx}"
            var_idx += 1

        grammar: Dict[str, List[str]] = {var: [] for var in state_to_var.values()}

        # 1. Transitions: Vi -> aVj
        # Sort states and symbols for deterministic production ordering
        for state in sorted(dfa.transitions.keys()):
            if state not in state_to_var:
                continue
            current_var = state_to_var[state]
            state_trans = dfa.transitions[state]
            for symbol in sorted(state_trans.keys()):
                next_state = state_trans[symbol]
                if next_state in state_to_var:
                    next_var = state_to_var[next_state]
                    production = f"{symbol}{next_var}"
                    if production not in grammar[current_var]:
                        grammar[current_var].append(production)

        # 2. Accept states: Vk -> ε (empty string)
        for state in sorted(dfa.accept_states):
            if state in state_to_var:
                current_var = state_to_var[state]
                if "" not in grammar[current_var]:
                    grammar[current_var].append("")

        return grammar

    @staticmethod
    def format_grammar(grammar: Dict[str, List[str]], start_symbol: str = "S") -> str:
        """
        Format a grammar dictionary into a clean, human-readable string.
        """
        ordered_symbols = [start_symbol] + sorted(
            symbol for symbol in grammar if symbol != start_symbol
        )
        lines = [f"Start symbol: {start_symbol}", "Productions:"]
        for symbol in ordered_symbols:
            if symbol not in grammar:
                continue
            rhs = " | ".join(
                "ε" if production == "" else production
                for production in grammar[symbol]
            )
            lines.append(f"  {symbol} -> {rhs}")
        return "\n".join(lines)
