import ollama
import json
from .models import LogicSpec, DFA
from .repair import DFARepairEngine

class BaseAgent:
    def __init__(self, model_name="qwen2.5-coder:1.5b"):
        self.model_name = model_name

    def call_ollama(self, system_prompt: str, user_prompt: str, format_schema=None) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        options = {'temperature': 0.1}
        api_params = {'model': self.model_name, 'messages': messages, 'options': options}
        if format_schema:
            api_params['format'] = format_schema
        
        try:
            response = ollama.chat(**api_params)
            return response['message']['content']
        except Exception as e:
            print(f"   [LLM Error] {e}")
            raise e

class AnalystAgent(BaseAgent):
    def analyze(self, user_prompt: str) -> LogicSpec:
        print(f"\n[Agent 1] Extracting Logic Variables...")
        
        # 1. Deterministic Heuristics
        heuristic_spec = LogicSpec.from_prompt(user_prompt)
        if heuristic_spec:
            print(f"   -> Extracted (Regex): {heuristic_spec.logic_type} | Target: '{heuristic_spec.target}'")
            return heuristic_spec

        # 2. LLM Fallback
        system_prompt = (
            "You are a Parameter Extractor. Output JSON only.\n"
            "Supported Types: STARTS_WITH, NOT_STARTS_WITH, ENDS_WITH, CONTAINS, DIVISIBLE_BY\n"
            "Extract the target substring or number exactly."
        )
        try:
            response = self.call_ollama(
                system_prompt, 
                user_prompt,
                format_schema=LogicSpec.model_json_schema()
            )
            data = json.loads(response)
            if 'alphabet' not in data or not data['alphabet']:
                data['alphabet'] = ["0", "1"]
            spec = LogicSpec(**data)
            print(f"   -> Extracted (LLM): {spec.logic_type} | Target: '{spec.target}'")
            return spec
        except Exception:
            # Absolute fallback
            return LogicSpec(logic_type="CONTAINS", target="a")

class ArchitectAgent(BaseAgent):
    def __init__(self, model_name):
        super().__init__(model_name)
        self.repair_engine = DFARepairEngine()

    def design(self, spec: LogicSpec, feedback: str = "") -> DFA:
        print(f"\n[Agent 2] Designing DFA... (Feedback: {feedback if feedback else 'None'})")
        
        system_prompt = (
            "You are a DFA Architect. Output VALID JSON.\n"
            f"Constraint: {spec.logic_type} '{spec.target}'\n"
            "STRATEGY:\n"
            "- STARTS_WITH: Branch on first char. Mismatch -> Dead State.\n"
            "- CONTAINS: Sequence matches. Final state loops forever (Trap Accept).\n"
            "- ENDS_WITH: Sequence matches. Backtrack on mismatch.\n"
            "q0 is always Start."
        )
        
        user_prompt = f"Target Alphabet: {spec.alphabet}"
        if feedback: user_prompt += f"\n\nFIX THIS ERROR: {feedback}"
        
        try:
            response_content = self.call_ollama(
                system_prompt, user_prompt, format_schema=DFA.model_json_schema()
            )
            data = json.loads(response_content)
            data['alphabet'] = spec.alphabet
            
            # Apply Auto-Repair immediately
            return self.repair_engine.auto_repair_dfa(data, spec)
        except Exception as e:
            print(f"   -> Architect Failed: {e}")
            raise e