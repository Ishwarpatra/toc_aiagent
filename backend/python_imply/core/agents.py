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
        
        # 🟢 FIX: Detailed System Prompt with EXAMPLES
        system_prompt = (
            f"""You are a Logic Analyst.
            Your job is to extract logical constraints into a JSON tree.
            
            ⛔ DO NOT DESIGN THE DFA.
            ⛔ DO NOT RETURN STATES OR TRANSITIONS.
            ✅ RETURN ONLY THE LOGIC SPECIFICATION.

            The JSON MUST match this schema exactly:
            {{
                "logic_type": "AND | OR | NOT | STARTS_WITH | ENDS_WITH | CONTAINS",
                "target": "string or null",
                "children": [ List of nested LogicSpecs ]
            }}

            ### EXAMPLES (FOLLOW THESE):
            
            Input: "starts with a"
            Output: {{ "logic_type": "STARTS_WITH", "target": "a", "children": [] }}

            Input: "starts with a and ends with b"
            Output: {{
                "logic_type": "AND",
                "target": null,
                "children": [
                    {{ "logic_type": "STARTS_WITH", "target": "a", "children": [] }},
                    {{ "logic_type": "ENDS_WITH", "target": "b", "children": [] }}
                ]
            }}

            Return JSON ONLY. No Markdown.
            """
        )
        
        try:
            resp = self.call_ollama(system_prompt, user_prompt)
            
            # Clean Markdown if present
            cleaned_resp = (
                resp.replace("```json", "")
                    .replace("```", "")
                    .strip()
            )
            
            # 1️⃣ Parse JSON manually first
            data = json.loads(cleaned_resp)

            # 🟢 FIX: Safety Guard - Check if LLM returned a DFA instead of Logic
            if "states" in data or "transitions" in data:
                print("   [Analyst Warning] LLM generated a DFA instead of LogicSpec. Retrying logic...")
                raise ValueError("LLM returned DFA states instead of logic tree.")

            # 2️⃣ Normalization Layer (Fix common LLM typos)
            if "type" in data and "logic_type" not in data:
                data["logic_type"] = data.pop("type")
            if "constraints" in data and "children" not in data:
                data["children"] = data.pop("constraints")
                
            # Normalize children recursively
            if "children" in data:
                for child in data["children"]:
                    if "type" in child and "logic_type" not in child:
                        child["logic_type"] = child.pop("type")

            # 3️⃣ Validate
            spec = LogicSpec.model_validate(data)
            spec.set_alphabet_recursive(detected_alphabet)
            return spec

        except Exception as e:
            print(f"   [Analyst Error] {e}")
            # Optional: Fallback to a simple CONTAINS if parsing fails completely
            # return LogicSpec(logic_type="CONTAINS", target="a", alphabet=detected_alphabet)
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