import ollama
import json
import re
from .models import LogicSpec, DFA
from .repair import DFARepairEngine
from .product import ProductConstructionEngine

class BaseAgent:
    def __init__(self, model_name="qwen2.5-coder:1.5b"):
        self.model_name = model_name

    def call_ollama(self, system, user, schema=None) -> str:
        options = {'temperature': 0.1}
        params = {'model': self.model_name, 'messages': [{'role':'system','content':system}, {'role':'user','content':user}], 'options': options}
        
        # Only apply schema if strictly provided
        if schema: 
            params['format'] = schema
            
        try:
            print("   ... (Sending request to Ollama) ...")
            response = ollama.chat(**params)
            return response['message']['content']
        except Exception as e:
            raise e

class AnalystAgent(BaseAgent):
    def analyze(self, user_prompt: str) -> LogicSpec:
        print(f"\n[Agent 1] Analyzing Request: '{user_prompt}'")
        
        # --- 1. DETECT ALPHABET GLOBALLY ---
        detected_alphabet = ['0', '1']
        if re.search(r"[a-z]", user_prompt.lower()):
            detected_alphabet = ['a', 'b']
        print(f"   -> Detected Alphabet: {detected_alphabet}")

        # --- 2. TRY HEURISTIC (Atomic) ---
        # Skip heuristic if complex logic keywords are present
        if " and " not in user_prompt.lower() and " or " not in user_prompt.lower():
            heuristic = LogicSpec.from_prompt(user_prompt)
            if heuristic: 
                print(f"   -> Detected Atomic: {heuristic.logic_type}")
                heuristic.set_alphabet_recursive(detected_alphabet)
                return heuristic

        # --- 3. ASK LLM (Recursive) ---
        print("   -> Complex logic detected. Asking LLM (Relaxed Mode)...")
        system_prompt = (
            "You are a Logic Extractor. Output VALID JSON only. Do not wrap in markdown.\n"
            "Recursive Logic:\n"
            "- 'A and B' -> logic_type='AND', children=[SpecA, SpecB]\n"
            "- 'A or B'  -> logic_type='OR', children=[SpecA, SpecB]\n"
            "- 'NOT (complex)' -> logic_type='NOT', children=[SpecA]\n"
            "Atomic types (PREFERRED for simple negation):\n"
            "- STARTS_WITH, NOT_STARTS_WITH\n"
            "- ENDS_WITH, NOT_ENDS_WITH\n"
            "- CONTAINS, NOT_CONTAINS\n"
            "Example: 'not end with a' -> {\"logic_type\": \"NOT_ENDS_WITH\", \"target\": \"a\"}\n"
        )
        
        try:
            resp = self.call_ollama(system_prompt, user_prompt)
            cleaned_resp = resp.replace("```json", "").replace("```", "").strip()
            spec = LogicSpec.model_validate_json(cleaned_resp)
            spec.set_alphabet_recursive(detected_alphabet)
            return spec
        except Exception as e:
            print(f"   [Analyst Error] {e}")
            raise ValueError("Could not parse logic.")

class ArchitectAgent(BaseAgent):
    def __init__(self, model_name):
        super().__init__(model_name)
        self.repair_engine = DFARepairEngine()
        self.product_engine = ProductConstructionEngine()

    def design(self, spec: LogicSpec) -> DFA:
        # --- RECURSIVE CASES ---
        if spec.logic_type == "NOT":
            print(f"\n[Architect] Recursively solving: NOT")
            
            # --- CRITICAL FIX: GUARD CLAUSE ---
            if not spec.children:
                print("   [Error] 'NOT' node missing children. Attempting fallback...")
                # If target exists, treat as atomic NOT_CONTAINS fallback? 
                # Or just raise clearer error.
                raise ValueError(f"Analyst generated 'NOT' without children. Target was: {spec.target}")

            child_dfa = self.design(spec.children[0])
            return self.product_engine.invert(child_dfa)

        if spec.logic_type in ["AND", "OR"]:
            print(f"\n[Architect] Recursively solving: {spec.logic_type}")
            dfa1 = self.design(spec.children[0])
            dfa2 = self.design(spec.children[1])
            return self.product_engine.combine(dfa1, dfa2, spec.logic_type)

        # --- BASE CASE (Atomic) ---
        print(f"\n[Architect] Designing Atomic: {spec.logic_type} '{spec.target}'")
        system_prompt = (
            "You are a DFA Architect. Output VALID JSON.\n"
            f"Task: Create DFA for {spec.logic_type} '{spec.target}'\n"
            "Use standard construction (q0 start, q_dead for traps)."
        )
        
        try:
            resp = self.call_ollama(system_prompt, f"Alphabet: {spec.alphabet}", DFA.model_json_schema())
            raw_data = json.loads(resp)
            raw_data['alphabet'] = spec.alphabet
            return self.repair_engine.auto_repair_dfa(raw_data, spec)
        except Exception as e:
            print(f"   -> Architect Failed: {e}")
            raise e