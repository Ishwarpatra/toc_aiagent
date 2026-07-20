import unittest
from core.models import DFA
from core.grammar import GrammarBuilder

class TestGrammarBuilder(unittest.TestCase):
    def test_dfa_to_grammar(self):
        # Simple DFA: accepts binary strings ending in 1
        # q0 --0--> q0, q0 --1--> q1, q1 --0--> q0, q1 --1--> q1
        # Start: q0, Accept: q1
        dfa = DFA(
            states={'q0', 'q1'},
            alphabet={'0', '1'},
            transitions={
                'q0': {'0': 'q0', '1': 'q1'},
                'q1': {'0': 'q0', '1': 'q1'}
            },
            start_state='q0',
            accept_states={'q1'}
        )
        
        grammar = GrammarBuilder.build_from_dfa(dfa)
        
        # Expected Grammar:
        # S -> 0S | 1A
        # A -> 0S | 1A | ''
        
        # S = q0, A = q1
        self.assertIn('0S', grammar['S'])
        self.assertIn('1A', grammar['S'])
        self.assertIn('0S', grammar['A'])
        self.assertIn('1A', grammar['A'])
        self.assertIn('', grammar['A'])
        self.assertNotIn('', grammar['S'])

    def test_format_grammar(self):
        grammar = {
            'S': ['0S', '1A'],
            'A': ['0S', '1A', '']
        }
        formatted = GrammarBuilder.format_grammar(grammar)
        self.assertIn("Start symbol: S", formatted)
        self.assertIn("Productions:", formatted)
        self.assertIn("  S -> 0S | 1A", formatted)
        self.assertIn("  A -> 0S | 1A | ε", formatted)

if __name__ == '__main__':
    unittest.main()
