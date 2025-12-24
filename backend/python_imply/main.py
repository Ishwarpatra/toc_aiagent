import os
import time
from core.validator import DeterministicValidator
from core.repair import DFARepairEngine
from core.agents import AnalystAgent, ArchitectAgent

# --- Configuration ---
MODEL_NAME = "qwen2.5-coder:1.5b" 

# --- Graphviz Path Fix ---
possible_paths = [
    r"C:\Program Files\Graphviz\bin",
    r"C:\Program Files (x86)\Graphviz\bin",
    "/usr/local/bin",
    "/usr/bin"
]
for path in possible_paths:
    if os.path.exists(path):
        os.environ["PATH"] += os.pathsep + path

class DFAGeneratorSystem:
    def __init__(self):
        self.validator = DeterministicValidator()
        self.analyst = AnalystAgent(MODEL_NAME)
        self.architect = ArchitectAgent(MODEL_NAME)
        self.repair_engine = DFARepairEngine()
        self.max_retries = 4
        print(f"--- System Initialized: Modular Architecture ({MODEL_NAME}) ---")

    def visualizer_tool(self, dfa):
        try:
            from graphviz import Digraph
            output_dir = "output"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            dot = Digraph(comment='DFA Visualization')
            dot.attr(rankdir='LR')
            dot.node('start_ptr', '', shape='none')
            dot.edge('start_ptr', dfa.start_state)
            for state in dfa.states:
                shape = 'doublecircle' if state in dfa.accept_states else 'circle'
                dot.node(state, state, shape=shape)
            for src, trans in dfa.transitions.items():
                for sym, dest in trans.items():
                    dot.edge(src, dest, label=str(sym))
            
            # SAVE TO OUTPUT FOLDER
            output_path = os.path.join(output_dir, 'dfa_result')
            output_file = dot.render(output_path, format='png')
            
            print(f"\n[Visualizer] Graph saved to {output_file}")
        except Exception as e:
            print(f"\n[Visualizer] skipped: {e}")

    # --- MAIN LOOP ---
    def run(self, user_query):
        start_time = time.time()
        
        # Agent 1: Analyze
        spec = self.analyst.analyze(user_query)
        feedback = ""
        
        for i in range(self.max_retries):
            # Agent 2: Architect (Includes Auto-Repair)
            dfa_obj = self.architect.design(spec, feedback)

            # ALWAYS validate via the deterministic validator for every logic type
            # (no special-case 'short-circuits' for parity or other problems).
            is_valid, error_msg = self.validator.validate(dfa_obj, spec)

            if is_valid:
                self.visualizer_tool(dfa_obj)
                print(f"\n--- SUCCESS in {time.time() - start_time:.4f}s ---")
                return

            # Auto-Repair: Inversion Attempt
            print("   [System] Validation Failed. Attempting Logic Inversion...")
            inverted_dfa = self.repair_engine.try_inversion_fix(dfa_obj, spec, self.validator)

            if inverted_dfa:
                print("\n   [Auto-Repair] INVERSION TRIGGERED!")
                self.visualizer_tool(inverted_dfa)
                print(f"\n--- SUCCESS (Via Inversion) in {time.time() - start_time:.4f}s ---")
                return

            # No shortcut: pass validator feedback back to architect for refinement.
            feedback = error_msg
            print(f">>> Retry {i+1}/{self.max_retries}...")
        
        print(f"\n--- FAILED after {time.time() - start_time:.4f}s ---")

if __name__ == "__main__":
    system = DFAGeneratorSystem()
    system.run("Design a DFA that accepts strings ending with 'ab'")