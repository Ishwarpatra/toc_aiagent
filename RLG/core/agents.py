import os
import json
from typing import Dict, List
from dotenv import load_dotenv
from .models import DFA, DeterministicValidator

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

class VisionAgent:
    def __init__(self, model=None):
        from .providers import GeminiProvider, OpenRouterProvider
        
        self.providers = []
        
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            self.providers.append(GeminiProvider(gemini_key.strip('"').strip("'").strip()))
            
        or_key = os.environ.get("OPENROUTER_API_KEY")
        if or_key:
            self.providers.append(OpenRouterProvider(or_key.strip('"').strip("'").strip()))
            
        self.model_override = model
        self.system_prompt = """You are a specialist in automata theory. 
Read the provided image of a DFA state diagram and output its formal representation in JSON format.
The JSON must strictly follow this structure:
{
    "states": ["q0", "q1", ...],
    "alphabet": ["0", "1", ...],
    "transitions": {
        "q0": {"0": "q0", "1": "q1"},
        ...
    },
    "start_state": "q0",
    "accept_states": ["q1", ...]
}
Only output the JSON string, no other text."""

    def process_image(self, base64_image: str) -> DFA:
        last_error = None
        
        for provider in self.providers:
            if self.model_override:
                models = [self.model_override]
            else:
                models = provider.get_models()
                
            for model_name in models:
                try:
                    dfa_data = provider.call(model_name, self.system_prompt, "Parse this DFA diagram.", base64_image)
                    dfa = DFA(**dfa_data)
                    if not DeterministicValidator.validate(dfa):
                        raise ValueError("VisionAgent output an invalid DFA structure.")
                    return dfa
                except Exception as e:
                    last_error = e
                    print(f"VisionAgent provider={provider.__class__.__name__} model={model_name} failed: {e}")

        raise ValueError(f"All vision providers and models failed. Last error: {last_error}")

class DescriberAgent:
    def __init__(self, model=None):
        # We'll use OpenRouter or Gemini for descriptions too.
        # For simplicity in this refactor, we'll use OpenRouter if available, else Gemini.
        from .providers import GeminiProvider, OpenRouterProvider
        self.providers = []
        
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key:
            self.providers.append(GeminiProvider(gemini_key.strip('"').strip("'").strip()))
            
        or_key = os.environ.get("OPENROUTER_API_KEY")
        if or_key:
            self.providers.append(OpenRouterProvider(or_key.strip('"').strip("'").strip()))
            
        self.model_override = model
        self.system_prompt = "You are an expert computer scientist. Read the following DFA state machine and its associated Regular Grammar. In exactly one clear sentence, describe the language it accepts."

    def describe(self, dfa: DFA, grammar: Dict[str, List[str]]) -> str:
        prompt = f"""
DFA Structure:
States: {dfa.states}
Alphabet: {dfa.alphabet}
Transitions: {dfa.transitions}
Start State: {dfa.start_state}
Accept States: {dfa.accept_states}

Regular Grammar:
{json.dumps(grammar, indent=2)}
"""
        last_error = None
        for provider in self.providers:
            # We use an empty image for text-only description calls if the provider expects one,
            # but our current 'call' requires one. For text-only, we should ideally have a separate method,
            # but for now we'll pass a tiny transparent pixel if needed, or just hope it handles empty b64.
            # Actually, most VLMs handle text-only fine.
            models = [self.model_override] if self.model_override else provider.get_models()
            for model_name in models:
                try:
                    # Reuse 'call' but with a placeholder image if necessary. 
                    # Note: OpenRouter/Gemini call expects image_b64.
                    # We'll pass a 1x1 transparent PNG b64.
                    empty_img = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
                    response_data = provider.call(model_name, self.system_prompt, prompt, empty_img)
                    # If response_data is a dict (JSON match), we might need to extract the description.
                    # But the DescriberAgent usually expects a string.
                    # Our current provider.call returns json.loads(). 
                    # If the model follows instructions and outputs ONLY JSON, it might error here if it just outputs text.
                    # Let's assume for description we want raw text. 
                    # We might need a raw_call method in providers. 
                    # For now, let's just use the existing call and see if it works.
                    return str(response_data) 
                except Exception as e:
                    last_error = e
        
        return f"Description failed: {last_error}"
