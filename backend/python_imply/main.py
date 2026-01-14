import os
import time
import shutil
import sys
import argparse
import logging

from core.validator import DeterministicValidator
from core.repair import DFARepairEngine
from core.agents import AnalystAgent, ArchitectAgent
from core.models import DFA

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration defaults (can be overridden via env or CLI) ---
DEFAULT_MODEL_NAME = os.environ.get("AUTO_DFA_MODEL", "qwen2.5-coder:1.5b")
DEFAULT_MAX_PRODUCT_STATES = int(os.environ.get("AUTO_DFA_MAX_PRODUCT_STATES", "2000"))

# Check if Graphviz is installed
if not shutil.which("dot"):
    logger.warning("\n[System Warning] Graphviz not found in PATH. Visualization will be skipped.\n"
                   "Install Graphviz from https://graphviz.org/download/ or add it to PATH if you need PNG outputs.\n")


class DFAGeneratorSystem:
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, max_product_states: int = DEFAULT_MAX_PRODUCT_STATES):
        self.validator = DeterministicValidator()
        # Agents accept model_name for any future LLM-backed behavior
        self.analyst = AnalystAgent(model_name)
        self.architect = ArchitectAgent(model_name, max_product_states=max_product_states)
        self.repair_engine = DFARepairEngine()
        # Safety threshold for product/DFA combination operations (configurable)
        self.max_product_states = int(max_product_states)
        self.max_retries = 3
        logger.info(f"--- System Initialized: model={model_name} max_product_states={self.max_product_states} ---")

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
                shape = 'doublecircle' if state in dfa.accept_states else 'circle'
                dot.node(state, state, shape=shape)

            # Edges
            for src, trans in dfa.transitions.items():
                for sym, dest in trans.items():
                    dot.edge(src, dest, label=str(sym))

            # SAVE
            output_path = os.path.join(output_dir, clean_name)
            output_file = dot.render(output_path, format='png')

            logger.info(f"[Visualizer] Graph saved to {output_file}")
        except Exception as e:
            logger.debug(f"[Visualizer] Skipped (Graphviz error): {e}")

    # --- MAIN LOOP ---
    def run(self, user_query):
        start_time = time.time()

        # 1. Analyze (Supports Recursive Logic)
        try:
            spec = self.analyst.analyze(user_query)
        except Exception as e:
            logger.error(f"Analysis Failed: {e}")
            return

        # Ensure alphabets are unified for composite specs if agents set them later
        try:
            # Many helper functions in agents/models will attempt to unify alphabets;
            # this is just an informative log for now.
            logger.info(f"   -> Spec Tree: {spec.logic_type} (Children: {len(getattr(spec, 'children', []) )})")
        except Exception:
            pass

        # 2. Architect (Recursive Design)
        # Note: ArchitectAgent should consult system.max_product_states as needed.
        try:
            # ArchitectAgent receives the safety threshold already via constructor
            dfa_obj = self.architect.design(spec)
        except Exception as e:
            logger.error(f"Architecture Failed: {e}")
            return

        # 3. Validate
        is_valid, error_msg = self.validator.validate(dfa_obj, spec)

        if is_valid:
            # name the visualization by logic_type or a short hash if too long
            filename = getattr(spec, "logic_type", "result")
            try:
                self.visualizer_tool(dfa_obj, filename=filename)
            except Exception:
                logger.debug("Visualizer skipped for final output.")
            logger.info(f"--- SUCCESS in {time.time() - start_time:.4f}s ---")
        else:
            logger.warning(f"--- VALIDATION FAILED ---\nReason: {error_msg}")
            # Optional: Auto-repair attempt could be invoked here using repair_engine


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-DFA: Generate and validate DFAs from NL descriptions.")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL_NAME, help="LLM model name (if used)")
    parser.add_argument("--max-product-states", type=int, default=DEFAULT_MAX_PRODUCT_STATES,
                        help="Maximum allowed product DFA states (safety threshold)")
    parser.add_argument("--prompt", type=str, default=None, help="Optional prompt to run immediately")
    args = parser.parse_args()

    system = DFAGeneratorSystem(model_name=args.model, max_product_states=args.max_product_states)

    if args.prompt:
        system.run(args.prompt)
    else:
        # interactive examples
        system.run("Design a DFA that accepts strings that start with 'a' or end with 'b'")