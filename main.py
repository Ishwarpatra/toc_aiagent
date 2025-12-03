import ollama
import json
import os
import re
from validator import DeterministicValidator, LogicSpec, DFA

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
        self.max_retries = 4
        print(f"--- System Initialized: Modular Architecture ({MODEL_NAME}) ---")

    def _call_ollama(self, system_prompt: str, user_prompt: str, format_schema=None) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        options = {'temperature': 0.1} 
        api_params = {'model': MODEL_NAME, 'messages': messages, 'options': options}
        if format_schema:
            api_params['format'] = format_schema
        
        try:
            response = ollama.chat(**api_params)
            return response['message']['content']
        except Exception as e:
            print(f"   [System] API Connection Error: {e}")
            raise e

    # --- AGENT 1: THE EXTRACTOR ---
    def agent_1_analyst(self, user_prompt: str) -> LogicSpec:
        print(f"\n[Agent 1] Extracting Logic Variables...")
        system_prompt = (
            "You are a Parameter Extractor. Your job is to convert natural language into variables.\n"
            "Supported Types:\n"
            "- STARTS_WITH (e.g. 'starts with b', 'begin with bb')\n"
            "- NOT_STARTS_WITH (e.g. 'does not start with b')\n"
            "- ENDS_WITH (e.g. 'ending in aba')\n"
            "- NOT_ENDS_WITH (e.g. 'not ending in a')\n"
            "- CONTAINS (e.g. 'containing bb')\n"
            "- NOT_CONTAINS (e.g. 'does not contain a')\n"
            "\n"
            "Extract the 'target' substring exactly."
        )
        
        try:
            response = self._call_ollama(
                system_prompt, 
                user_prompt,
                format_schema=LogicSpec.model_json_schema()
            )
            data = json.loads(response)
            data['logic_type'] = data['logic_type'].upper()
            
            if not data['target']:
                match = re.search(r"['\"](.*?)['\"]", user_prompt)
                if match: data['target'] = match.group(1)

            spec = LogicSpec(**data)
            print(f"   -> Extracted: {spec.logic_type} | Target: '{spec.target}'")
            return spec
        except Exception as e:
            print(f"   [Agent 1 Error] {e}")
            return LogicSpec(logic_type="CONTAINS", target="a")

    # --- AGENT 2: THE ARCHITECT ---
    def agent_2_architect(self, spec: LogicSpec, feedback: str = "") -> DFA:
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
            response_content = self._call_ollama(
                system_prompt, user_prompt, format_schema=DFA.model_json_schema()
            )
            data = json.loads(response_content)
            data['alphabet'] = spec.alphabet
            return self._auto_repair_dfa(data, spec)
        except Exception as e:
            print(f"   -> Architect Failed: {e}")
            raise e

    # --- AUTO-REPAIR ENGINE (CHAIN BUILDER UPGRADE) ---
    def _auto_repair_dfa(self, data: dict, spec: LogicSpec) -> DFA:
        states = set(data.get('states', []))
        transitions = data.get('transitions', {})
        alphabet = spec.alphabet
        accept_states = set(data.get('accept_states', []))

        # 1. Structure Init
        for src, paths in transitions.items():
            states.add(src)
            for _, dest in paths.items(): states.add(dest)
        
        clean_states = sorted([s for s in states if len(s) < 10 and " " not in s])
        if not clean_states: clean_states = ["q0", "q1"]
        start_state = data.get('start_state', clean_states[0])
        if start_state not in clean_states: start_state = clean_states[0]
        
        if "q_dead" not in clean_states: clean_states.append("q_dead")
        transitions["q_dead"] = {s: "q_dead" for s in alphabet}

        # 2. Logic Overwrites
        type_str = spec.logic_type
        target = spec.target

        # --- SPECIAL HANDLER: STARTS_WITH CHAIN BUILDER ---
        # Instead of patching, we BUILD the correct chain for the target string.
        # This fixes the "bb" vs "b" issue by creating q0 -> q1 -> q2.
        if type_str == "STARTS_WITH" and target:
            print(f"   [Auto-Repair] Rebuilding Chain for STARTS_WITH '{target}'")
            
            # Ensure we have enough states (q0, q1, q2... for len(target))
            # If target is 'bb' (len 2), we need 3 states: Start(0), Partial(1), Accept(2)
            required_states = [start_state]
            for i in range(len(target)):
                st_name = f"q{i+1}"
                if st_name not in clean_states: clean_states.append(st_name)
                required_states.append(st_name)
            
            # The last state in the chain is the ONLY Accept state
            final_state = required_states[-1]
            accept_states = {final_state}
            
            # Build the Chain
            for i, current_st in enumerate(required_states[:-1]):
                char_to_match = target[i]
                next_st = required_states[i+1]
                
                if current_st not in transitions: transitions[current_st] = {}
                
                # Correct Path
                transitions[current_st][char_to_match] = next_st
                
                # Incorrect Paths (All other chars go to Dead)
                for char in alphabet:
                    if char != char_to_match:
                        transitions[current_st][char] = "q_dead"

            # Latch the Final State (Loop forever on everything)
            if final_state not in transitions: transitions[final_state] = {}
            transitions[final_state] = {s: final_state for s in alphabet}

        # --- SPECIAL HANDLER: NOT_STARTS_WITH ---
        elif type_str == "NOT_STARTS_WITH" and target:
            # Simple case: First char match -> Dead. Others -> Safe (Latch Accept)
            first_char = target[0]
            if start_state not in transitions: transitions[start_state] = {}
            
            for char in alphabet:
                if char == first_char:
                    transitions[start_state][char] = "q_dead"
                else:
                    # If we start with something else, we are safe forever.
                    # Create a generic accept state 'q_safe'
                    safe = "q1"
                    if safe not in clean_states: clean_states.append(safe)
                    if safe not in transitions: transitions[safe] = {}
                    
                    transitions[start_state][char] = safe
                    transitions[safe] = {s: safe for s in alphabet}
                    accept_states.add(safe)
            
            # Empty string logic?
            # "Not starts with b": Empty string technically doesn't start with b.
            accept_states.add(start_state)

        # --- GENERAL REPAIR (For Contains / Ends With) ---
        else:
            for state in clean_states:
                if state not in transitions: transitions[state] = {}
                for symbol in alphabet:
                    if symbol not in transitions[state]:
                        if "CONTAINS" in type_str and state in accept_states:
                             transitions[state][symbol] = state
                        elif "NOT_CONTAINS" in type_str and state == "q_dead":
                             transitions[state][symbol] = state
                        else:
                            transitions[state][symbol] = start_state

        data['states'] = sorted(list(clean_states))
        data['transitions'] = transitions
        data['start_state'] = start_state
        data['accept_states'] = list(accept_states)
        return DFA(**data)

    # --- VISUALIZER ---
    def visualizer_tool(self, dfa: DFA):
        try:
            from graphviz import Digraph
            dot = Digraph(comment='DFA Visualization')
            dot.attr(rankdir='LR')
            dot.node('start_ptr', '', shape='none')
            dot.edge('start_ptr', dfa.start_state)

            for state in dfa.states:
                shape = 'doublecircle' if state in dfa.accept_states else 'circle'
                dot.node(state, state, shape=shape)
                
            for src, trans in dfa.transitions.items():
                for sym, dest in trans.items():
                    dot.edge(src, dest, label=sym)
            output_file = dot.render('dfa_result', format='png')
            print(f"\n[Visualizer] Graph saved to {output_file}")
            os.startfile(output_file)
        except Exception as e:
            print(f"\n[Visualizer] skipped: {e}")

    # --- MAIN LOOP ---
    def run(self, user_query):
        spec = self.agent_1_analyst(user_query)
        feedback = ""
        for i in range(self.max_retries):
            dfa_obj = self.agent_2_architect(spec, feedback)
            is_valid, error_msg = self.validator.validate(dfa_obj, spec)
            
            if is_valid:
                self.visualizer_tool(dfa_obj)
                print("\n--- SUCCESS ---")
                return
            else:
                feedback = error_msg
                print(f">>> Retry {i+1}/{self.max_retries}...")
        print("\n--- FAILED ---")

if __name__ == "__main__":
    system = DFAGeneratorSystem()
    query = "Design a DFA that accepts strings not starting with 'bb'"
    print(f"\n>>> Running Challenge: {query}")
    system.run(query)