import os
import time
import sys
import argparse
import logging

from core.validator import DeterministicValidator
from core.repair import DFARepairEngine, LLMConnectionError
from core.agents import AnalystAgent, ArchitectAgent
from core.models import DFA

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration defaults (can be overridden via env or CLI) ---
DEFAULT_MODEL_NAME = os.environ.get("AUTO_DFA_MODEL", "qwen2.5-coder:1.5b")
DEFAULT_MAX_PRODUCT_STATES = int(os.environ.get("AUTO_DFA_MAX_PRODUCT_STATES", "2000"))


class DFAGeneratorSystem:
    """
    Main DFA Generator System that orchestrates analysis, architecture,
    validation, and repair of DFAs from natural language descriptions.

    Note: Server-side visualization has been removed. The frontend handles
    all DFA rendering using Mermaid.js. This eliminates the Graphviz
    dependency for typical usage.
    
    CRITICAL: Implements Context Manager protocol for deterministic resource cleanup.
    Always use with 'with DFAGeneratorSystem() as system:' to ensure cache is properly closed.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, max_product_states: int = DEFAULT_MAX_PRODUCT_STATES):
        self.validator = DeterministicValidator()
        # Agents accept model_name for LLM-backed behavior
        self.analyst = AnalystAgent(model_name)
        self.architect = ArchitectAgent(model_name, max_product_states=max_product_states)
        self.repair_engine = DFARepairEngine(model_name=model_name)
        # Safety threshold for product/DFA combination operations (configurable)
        self.max_product_states = int(max_product_states)
        self.max_retries = 3
        logger.info(f"--- System Initialized: model={model_name} max_product_states={self.max_product_states} ---")

    def __enter__(self) -> 'DFAGeneratorSystem':
        """Context manager entry - returns self for use in with block."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        Context manager exit - guarantees cache cleanup regardless of exception.
        
        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised
            
        Returns:
            False to propagate any exception, True to suppress it
        """
        self.close()
        return False  # Do not suppress exceptions

    def close(self) -> None:
        """
        CRITICAL: Explicitly close diskcache to flush WAL buffer to disk.
        Must be called before process exit to prevent cache data loss.
        """
        try:
            self.architect.cache.close()
            logger.debug("[Cache] diskcache flushed and closed")
        except Exception as e:
            logger.warning(f"[Cache] Failed to close: {e}")

    def __del__(self):
        """Destructor ensures cache is closed when object is garbage collected."""
        self.close()

    def export_to_json(self, dfa: DFA, filename: str = 'dfa_result') -> str:
        """
        Export DFA to a JSON file for frontend consumption.
        The frontend renders the DFA using Mermaid.js.
        
        Args:
            dfa: The DFA object to export
            filename: Name of the output file (without extension)
            
        Returns:
            Path to the exported JSON file
        """
        import json
        
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        clean_name = filename.replace(" ", "_").lower()
        output_path = os.path.join(output_dir, f"{clean_name}.json")
        
        with open(output_path, 'w') as f:
            json.dump(dfa.model_dump(), f, indent=2)
        
        logger.info(f"[Export] DFA JSON saved to {output_path}")
        return output_path

    # --- MAIN LOOP ---
    def run(self, user_query: str, export_json: bool = True):
        """
        Main execution loop for DFA generation.
        
        Args:
            user_query: Natural language description of the desired DFA
            export_json: Whether to export the result to JSON file
            
        Returns:
            Tuple of (DFA object, is_valid boolean, error_message)
        """
        start_time = time.time()

        # 1. Analyze (with retry / fallback)
        spec = None
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                spec = self.analyst.analyze(user_query)
                break
            except LLMConnectionError as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = 2 ** (attempt - 1)  # 1s, 2s, 4s
                    logger.warning(f"Analysis attempt {attempt}/{self.max_retries} failed (LLM unavailable), retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"Analysis failed after {self.max_retries} attempts: {e}")
            except Exception as e:
                logger.error(f"Analysis Failed: {e}")
                return None, False, str(e)

        if spec is None:
            return None, False, f"LLM service unavailable after {self.max_retries} retries: {last_error}"

        # Log spec tree info
        try:
            logger.info(f"   -> Spec Tree: {spec.logic_type} (Children: {len(getattr(spec, 'children', []))})")
        except Exception:
            pass

        # 2. Architect (with retry / fallback)
        dfa_obj = None
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                dfa_obj = self.architect.design(spec)
                break
            except LLMConnectionError as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = 2 ** (attempt - 1)
                    logger.warning(f"Architecture attempt {attempt}/{self.max_retries} failed (LLM unavailable), retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"Architecture failed after {self.max_retries} attempts: {e}")
            except Exception as e:
                logger.error(f"Architecture Failed: {e}")
                return None, False, str(e)

        if dfa_obj is None:
            return None, False, f"LLM service unavailable after {self.max_retries} retries: {last_error}"

        # 3. Validate
        is_valid, error_msg = self.validator.validate(dfa_obj, spec)

        # 4. Attempt repair if validation failed
        if not is_valid:
            logger.warning(f"Initial validation failed: {error_msg}")
            logger.info("Attempting LLM-based repair...")
            
            try:
                repaired_dfa = self.repair_engine.auto_repair_dfa(
                    data=dfa_obj.model_dump(),
                    spec=spec,
                    validator_instance=self.validator,
                    validation_error=error_msg
                )
                
                # Re-validate repaired DFA
                is_valid, error_msg = self.validator.validate(repaired_dfa, spec)
                if is_valid:
                    dfa_obj = repaired_dfa
                    logger.info("Repair successful!")
                    
            except LLMConnectionError as e:
                logger.warning(f"LLM repair unavailable: {e}")
            except Exception as e:
                logger.warning(f"Repair failed: {e}")

        if is_valid:
            filename = getattr(spec, "logic_type", "result")
            if export_json:
                try:
                    self.export_to_json(dfa_obj, filename=filename)
                except Exception:
                    logger.debug("JSON export skipped.")
            logger.info(f"--- SUCCESS in {time.time() - start_time:.4f}s ---")
        else:
            logger.warning(f"--- VALIDATION FAILED ---\nReason: {error_msg}")

        return dfa_obj, is_valid, error_msg


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-DFA: Generate and validate DFAs from NL descriptions.")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL_NAME, help="LLM model name")
    parser.add_argument("--max-product-states", type=int, default=DEFAULT_MAX_PRODUCT_STATES,
                        help="Maximum allowed product DFA states (safety threshold)")
    parser.add_argument("--prompt", type=str, default=None, help="Prompt to run immediately")
    parser.add_argument("--no-export", action="store_true", help="Disable JSON file export")
    args = parser.parse_args()

    system = DFAGeneratorSystem(model_name=args.model, max_product_states=args.max_product_states)

    if args.prompt:
        system.run(args.prompt, export_json=not args.no_export)
    else:
        # Interactive example
        system.run("Design a DFA that accepts strings that start with 'a' or end with 'b'")