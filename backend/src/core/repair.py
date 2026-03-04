"""
DFA Repair Engine

This module provides LLM-based repair for generated DFAs when validation fails.
Instead of hardcoded if/else templates, it uses the LLM to regenerate or fix
the DFA structure based on validator feedback.
"""

import json
import logging
from typing import Optional, List, Dict, Any, Tuple

from .models import DFA, LogicSpec
from .optimizer import cleanup_dfa

logger = logging.getLogger(__name__)


class LLMConnectionError(Exception):
    """Raised when the LLM service (Ollama) is unreachable."""
    pass


class DFARepairEngine:
    """
    LLM-based DFA repair engine that uses validator feedback to iteratively
    fix or regenerate DFA structures.
    """
    
    def __init__(self, model_name: str = "qwen2.5-coder:1.5b"):
        self.model_name = model_name
        self.max_repair_attempts = 3
    
    def _call_ollama(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """
        Call Ollama LLM service for DFA repair.
        Raises LLMConnectionError if service is unreachable.
        """
        try:
            import requests
            
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": user_prompt,
                    "system": system_prompt,
                    "stream": False
                },
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json().get("response", "")
            elif response.status_code == 404:
                raise LLMConnectionError(f"Model '{self.model_name}' not found. Please pull it first.")
            else:
                raise LLMConnectionError(f"Ollama returned status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            raise LLMConnectionError("Ollama service is not running. Start it with 'ollama serve'.")
        except requests.exceptions.Timeout:
            raise LLMConnectionError("Ollama request timed out. The model may be overloaded.")
        except Exception as e:
            logger.error(f"[RepairEngine] LLM call failed: {e}")
            raise LLMConnectionError(f"LLM service error: {str(e)}")
    
    def _parse_dfa_json(self, response: str, alphabet: List[str]) -> Optional[Dict]:
        """
        Parse LLM response into a valid DFA dictionary.
        """
        try:
            # Clean up typical LLM formatting
            cleaned = response.replace("```json", "").replace("```", "").strip()
            
            # Try to find JSON object in response
            start_idx = cleaned.find("{")
            end_idx = cleaned.rfind("}") + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.warning("[RepairEngine] No JSON object found in LLM response")
                return None
            
            json_str = cleaned[start_idx:end_idx]
            data = json.loads(json_str)
            
            # Normalize and validate required fields
            required_fields = ["states", "start_state", "accept_states", "transitions"]
            for field in required_fields:
                if field not in data:
                    logger.warning(f"[RepairEngine] Missing field: {field}")
                    return None
            
            # Ensure alphabet is set correctly
            data["alphabet"] = alphabet
            
            return data
            
        except json.JSONDecodeError as e:
            logger.warning(f"[RepairEngine] JSON parse error: {e}")
            return None
    
    def _build_repair_prompt(self, spec: LogicSpec, validation_error: str, 
                             previous_dfa: Optional[DFA] = None) -> Tuple[str, str]:
        """
        Build system and user prompts for LLM-based repair.
        """
        system_prompt = """You are a DFA (Deterministic Finite Automaton) expert.
Your task is to design or fix a DFA based on the given specification and error feedback.

CRITICAL RULES:
1. Output ONLY a valid JSON object with these keys: states, start_state, accept_states, transitions
2. The DFA must be COMPLETE - every state must have a transition for every alphabet symbol
3. Use simple state names like "q0", "q1", "q2", etc.
4. Transitions should be nested dicts: {"q0": {"a": "q1", "b": "q0"}}
5. Do NOT include any commentary or explanation - just the JSON

Example output format:
{
  "states": ["q0", "q1", "q2"],
  "start_state": "q0",
  "accept_states": ["q1"],
  "transitions": {
    "q0": {"a": "q1", "b": "q2"},
    "q1": {"a": "q1", "b": "q0"},
    "q2": {"a": "q0", "b": "q2"}
  }
}"""
        
        user_prompt_parts = [
            f"Design a DFA for the following specification:",
            f"- Logic Type: {spec.logic_type}",
            f"- Target: {spec.target or 'N/A'}",
            f"- Alphabet: {spec.alphabet}",
        ]
        
        if validation_error:
            user_prompt_parts.append(f"\nPREVIOUS VALIDATION ERROR:")
            user_prompt_parts.append(f"{validation_error}")
            user_prompt_parts.append("\nFix the DFA to address this error.")
        
        if previous_dfa:
            user_prompt_parts.append(f"\nPREVIOUS DFA (that failed validation):")
            user_prompt_parts.append(json.dumps(previous_dfa.model_dump(), indent=2))
        
        user_prompt_parts.append("\nOutput the corrected DFA JSON now:")
        
        return system_prompt, "\n".join(user_prompt_parts)
    
    def repair_with_llm(self, spec: LogicSpec, validation_error: str,
                        previous_dfa: Optional[DFA] = None,
                        validator_instance=None) -> Optional[DFA]:
        """
        Use LLM to repair a DFA based on validator feedback.
        
        Args:
            spec: The LogicSpec describing what the DFA should accept
            validation_error: The error message from the validator
            previous_dfa: The DFA that failed validation (if any)
            validator_instance: Validator to check repaired DFA
            
        Returns:
            A repaired DFA if successful, None otherwise
            
        Raises:
            LLMConnectionError: If the LLM service is unreachable
        """
        logger.info(f"[RepairEngine] Attempting LLM-based repair for {spec.logic_type}")
        
        for attempt in range(1, self.max_repair_attempts + 1):
            logger.info(f"[RepairEngine] Repair attempt {attempt}/{self.max_repair_attempts}")
            
            system_prompt, user_prompt = self._build_repair_prompt(
                spec, validation_error, previous_dfa
            )
            
            try:
                response = self._call_ollama(system_prompt, user_prompt)
                
                if not response:
                    logger.warning("[RepairEngine] Empty response from LLM")
                    continue
                
                dfa_data = self._parse_dfa_json(response, spec.alphabet)
                
                if not dfa_data:
                    validation_error = "Failed to parse DFA JSON from response"
                    continue
                
                # Build and validate the repaired DFA
                try:
                    repaired_dfa = DFA(**dfa_data)
                    repaired_dfa = cleanup_dfa(repaired_dfa, verbose=False)
                    
                    if validator_instance:
                        is_valid, error_msg = validator_instance.validate(repaired_dfa, spec)
                        if is_valid:
                            logger.info(f"[RepairEngine] Repair successful on attempt {attempt}")
                            return repaired_dfa
                        else:
                            logger.info(f"[RepairEngine] Repaired DFA failed validation: {error_msg}")
                            validation_error = error_msg
                            previous_dfa = repaired_dfa
                    else:
                        # No validator provided, return the parsed DFA
                        return repaired_dfa
                        
                except Exception as e:
                    logger.warning(f"[RepairEngine] DFA construction failed: {e}")
                    validation_error = str(e)
                    
            except LLMConnectionError:
                raise  # Re-raise connection errors
            except Exception as e:
                logger.error(f"[RepairEngine] Unexpected error: {e}")
                validation_error = str(e)
        
        logger.warning("[RepairEngine] All repair attempts failed")
        return None
    
    def auto_repair_dfa(self, data: dict, spec: LogicSpec, 
                        validator_instance=None,
                        validation_error: str = "") -> DFA:
        """
        Main entry point for DFA repair.
        
        Attempts LLM-based repair first. Falls back to basic structural
        cleanup if LLM is unavailable.
        
        Args:
            data: Raw DFA data dict (potentially malformed)
            spec: The LogicSpec for this DFA
            validator_instance: Optional validator for checking repairs
            validation_error: Error message that triggered repair
            
        Returns:
            A repaired DFA object
        """
        alphabet = spec.alphabet or ['0', '1']
        
        # Try LLM-based repair first
        try:
            previous_dfa = None
            if data.get('states') and data.get('transitions'):
                try:
                    data['alphabet'] = alphabet
                    previous_dfa = DFA(**data)
                except Exception:
                    pass
            
            repaired = self.repair_with_llm(
                spec=spec,
                validation_error=validation_error or "DFA failed initial validation",
                previous_dfa=previous_dfa,
                validator_instance=validator_instance
            )
            
            if repaired:
                return repaired
                
        except LLMConnectionError as e:
            logger.warning(f"[RepairEngine] LLM unavailable: {e}")
            # Fall through to basic cleanup
        
        # Fallback: Basic structural cleanup (no logic injection)
        logger.info("[RepairEngine] Falling back to basic structural cleanup")
        return self._basic_structural_cleanup(data, spec)
    
    def _basic_structural_cleanup(self, data: dict, spec: LogicSpec) -> DFA:
        """
        Perform basic structural cleanup on a DFA without logic injection.
        This is a fallback when LLM is unavailable.
        """
        alphabet = spec.alphabet or ['0', '1']
        
        states = list(set(data.get('states', ['q0', 'q1'])))
        
        # Filter out invalid state names
        clean_states = [s for s in states if len(s) < 15 and " " not in s]
        if not clean_states:
            clean_states = ["q0", "q1"]
        
        start_state = data.get('start_state', clean_states[0])
        if start_state not in clean_states:
            start_state = clean_states[0]
        
        accept_states = [s for s in data.get('accept_states', []) if s in clean_states]
        
        # Clean transitions
        raw_transitions = data.get('transitions', {})
        transitions = {}
        
        for state in clean_states:
            transitions[state] = {}
            state_trans = raw_transitions.get(state, {})
            
            for symbol in alphabet:
                dest = state_trans.get(symbol)
                if dest and dest in clean_states:
                    transitions[state][symbol] = dest
                else:
                    # Route undefined transitions to first state (or self)
                    transitions[state][symbol] = clean_states[0]
        
        dfa_data = {
            'states': sorted(clean_states),
            'alphabet': alphabet,
            'transitions': transitions,
            'start_state': start_state,
            'accept_states': sorted(accept_states),
            'reasoning': 'Basic structural cleanup applied (LLM unavailable)'
        }
        
        raw_dfa = DFA(**dfa_data)
        return cleanup_dfa(raw_dfa, verbose=False)
    
    def try_inversion_fix(self, dfa: DFA, spec: LogicSpec, 
                          validator_instance) -> Optional[DFA]:
        """
        Try inverting accept/reject states as a quick fix.
        
        This is useful when the DFA logic is correct but inverted
        (e.g., accepting complement of target language).
        """
        new_accept = [s for s in dfa.states if s not in dfa.accept_states]
        
        inverted = DFA(
            states=dfa.states,
            alphabet=dfa.alphabet,
            transitions=dfa.transitions,
            start_state=dfa.start_state,
            accept_states=new_accept,
            reasoning=(dfa.reasoning or "") + " (Accept states inverted)"
        )
        
        is_valid, _ = validator_instance.validate(inverted, spec)
        if is_valid:
            return inverted
        
        return None