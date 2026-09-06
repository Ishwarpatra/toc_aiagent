import unittest
from core.models import DFA, DeterministicValidator

class TestModels(unittest.TestCase):
    def test_valid_dfa(self):
        dfa = DFA(
            states={'q0', 'q1'},
            alphabet={'0', '1'},
            transitions={'q0': {'0': 'q0', '1': 'q1'}, 'q1': {'0': 'q0', '1': 'q1'}},
            start_state='q0',
            accept_states={'q1'}
        )
        self.assertTrue(DeterministicValidator.validate(dfa))

    def test_invalid_start_state(self):
        dfa = DFA(
            states={'q0'},
            alphabet={'0'},
            transitions={'q0': {'0': 'q0'}},
            start_state='q1',
            accept_states={'q0'}
        )
        self.assertFalse(DeterministicValidator.validate(dfa))

    def test_invalid_accept_state(self):
        dfa = DFA(
            states={'q0'},
            alphabet={'0'},
            transitions={'q0': {'0': 'q0'}},
            start_state='q0',
            accept_states={'q1'}
        )
        self.assertFalse(DeterministicValidator.validate(dfa))

if __name__ == '__main__':
    unittest.main()
