import os
import time
from core.validator import DeterministicValidator
from core.repair import DFARepairEngine
from core.agents import AnalystAgent, ArchitectAgent
from core.models import DFA

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
        self.max_retries = 3
        print(f"--- System Initialized: Modular Architecture ({MODEL_NAME}) ---")

    def visualizer_tool(self, dfa: DFA, filename='dfa_result'):
        try:
            from graphviz import Digraph
            output_dir = "output"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Create a clean filename
            clean_name = filename.replace(" ", "_").lower()
            dot = Digraph(comment='DFA Visualization')
            dot.attr(rankdir='LR')
            
            # Start Pointer
            dot.node('start_ptr', '', shape='none')
            dot.edge('start_ptr', dfa.start_state)
            
            # Nodes
            for state in dfa.states:
                # readable_state = state.replace("_", "\n") # Optional: multiline for composite
                shape = 'doublecircle' if state in dfa.accept_states else 'circle'
                dot.node(state, state, shape=shape)
            
            # Edges
            for src, trans in dfa.transitions.items():
                for sym, dest in trans.items():
                    dot.edge(src, dest, label=str(sym))
            
            # SAVE
            output_path = os.path.join(output_dir, clean_name)
            output_file = dot.render(output_path, format='png')
            
            print(f"\n[Visualizer] Graph saved to {output_file}")
        except Exception as e:
            print(f"\n[Visualizer] Skipped (Graphviz error): {e}")

    # --- MAIN LOOP ---
    def run(self, user_query):
        start_time = time.time()
        
        # 1. Analyze (Supports Recursive Logic)
        try:
            spec = self.analyst.analyze(user_query)
        except Exception as e:
            print(f"Analysis Failed: {e}")
            return

        print(f"   -> Spec Tree: {spec.logic_type} (Children: {len(spec.children)})")

        # 2. Architect (Recursive Design)
        # Note: Feedback loop is temporarily disabled for composite logic complexity
        try:
            dfa_obj = self.architect.design(spec)
        except Exception as e:
            print(f"Architecture Failed: {e}")
            return

        # 3. Validate
        is_valid, error_msg = self.validator.validate(dfa_obj, spec)

        if is_valid:
            self.visualizer_tool(dfa_obj, filename=spec.logic_type)
            print(f"\n--- SUCCESS in {time.time() - start_time:.4f}s ---")
        else:
            print(f"\n--- VALIDATION FAILED ---")
            print(f"Reason: {error_msg}")
            # Optional: Add simple retry logic here if needed, 
            # but composite repair is complex.

if __name__ == "__main__":
    system = DFAGeneratorSystem()
    # Test NOT logic
    system.run("Strings that start with 'a' OR (contain 'bb' AND do not end with 'a'")