from typing import Dict, List
from .models import DFA

class GrammarBuilder:
    @staticmethod
    def build_from_dfa(dfa: DFA) -> Dict[str, List[str]]:
        """
        Converts a DFA to a Right-Linear Grammar.
        
        Rules:
        1. Map each DFA state to an uppercase letter (q0 -> S, q1 -> A, ...).
        2. If q0 --a--> q1, then S -> aA.
        3. If q0 is an accept state, then S -> epsilon (represented as empty string '').
        """
        # Mapping DFA states to uppercase letters
        # S is always the start state
        state_to_var = {dfa.start_state: 'S'}
        
        # Available uppercase letters excluding S
        import string
        available_vars = [c for c in string.ascii_uppercase if c != 'S']
        
        var_idx = 0
        for state in dfa.states:
            if state != dfa.start_state:
                if var_idx < len(available_vars):
                    state_to_var[state] = available_vars[var_idx]
                    var_idx += 1
                else:
                    # Fallback if there are more than 26 states
                    state_to_var[state] = f"V{var_idx}"
                    var_idx += 1
        
        grammar: Dict[str, List[str]] = {var: [] for var in state_to_var.values()}
        
        # Transitions: S -> aA
        for state, transitions in dfa.transitions.items():
            current_var = state_to_var[state]
            for char, next_state in transitions.items():
                next_var = state_to_var[next_state]
                grammar[current_var].append(f"{char}{next_var}")
        
        # Accept states: S -> '' (epsilon)
        for state in dfa.accept_states:
            current_var = state_to_var[state]
            if '' not in grammar[current_var]:
                grammar[current_var].append('')
                
        return grammar

    @staticmethod
    def format_grammar(grammar: Dict[str, List[str]], start_symbol: str = "S") -> str:
        ordered_symbols = [start_symbol] + sorted(symbol for symbol in grammar if symbol != start_symbol)
        lines = [f"Start symbol: {start_symbol}", "Productions:"]
        for symbol in ordered_symbols:
            if symbol not in grammar:
                continue
            rhs = " | ".join("ε" if production == "" else production for production in grammar[symbol])
            lines.append(f"  {symbol} -> {rhs}")
        return "\n".join(lines)
