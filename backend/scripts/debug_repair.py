import json
import sys, os
# Ensure backend root is on sys.path when running this script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.agents import AnalystAgent, ArchitectAgent, BaseAgent

base = BaseAgent()
agent = AnalystAgent(base)
architect = ArchitectAgent(base)

spec = agent.analyze("Design a DFA that accepts strings starting with '0'")

fake_response = json.dumps({
    "states": ["q0", "q1", "q2"],
    "start_state": "q0",
    "accept_states": ["q1"],
    "transitions": {
        "q0": {"0": "q1", "1": "q2"},
        "q1": {"0": "q1", "1": "q1"},
        "q2": {"0": "q2", "1": "q2"}
    }
})

data = json.loads(fake_response)
dfa = architect.repair_engine.auto_repair_dfa(data, spec)
print("Resulting transitions:")
print(json.dumps(dfa.transitions, indent=2))
print("Spec alphabet:", spec.alphabet)
print("Clean states:", dfa.states)
print("Start state:", dfa.start_state)
print("Accept states:", dfa.accept_states)
