import ollama
import json
import os
import re
import time
from typing import Optional 
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
            "- STARTS_WITH (e.g. 'starts with b')\n"
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

    # --- AUTO-REPAIR ENGINE ---
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

        # --- SPECIAL HANDLER: STARTS_WITH CHAIN ---
        if type_str == "STARTS_WITH" and target:
            print(f"   [Auto-Repair] Rebuilding Chain for STARTS_WITH '{target}'")
            required_states = [start_state]
            for i in range(len(target)):
                st_name = f"q{i+1}"
                if st_name not in clean_states: clean_states.append(st_name)
                required_states.append(st_name)
            
            final_state = required_states[-1]
            accept_states = {final_state}
            
            for i, current_st in enumerate(required_states[:-1]):
                char_to_match = target[i]
                next_st = required_states[i+1]
                
                # FORCE OVERWRITE
                if current_st not in transitions: transitions[current_st] = {}
                transitions[current_st][char_to_match] = next_st
                
                for char in alphabet:
                    if char != char_to_match: 
                        transitions[current_st][char] = "q_dead"

            if final_state not in transitions: transitions[final_state] = {}
            transitions[final_state] = {s: final_state for s in alphabet}

        # --- SPECIAL HANDLER: NOT_STARTS_WITH CHAIN ---
        elif type_str == "NOT_STARTS_WITH" and target:
            print(f"   [Auto-Repair] Rebuilding Negative Chain for NOT_STARTS_WITH '{target}'")
            
            chain_states = [start_state]
            for i in range(len(target)):
                st_name = f"q{i+1}"
                if st_name not in clean_states: clean_states.append(st_name)
                chain_states.append(st_name)
            
            safe_state = "q_safe"
            if safe_state not in clean_states: clean_states.append(safe_state)
            if safe_state not in transitions: transitions[safe_state] = {}
            transitions[safe_state] = {s: safe_state for s in alphabet}
            
            accept_states = set(chain_states[:-1])
            accept_states.add(safe_state)
            
            for i, current_st in enumerate(chain_states[:-1]):
                bad_char = target[i]
                
                if current_st not in transitions: transitions[current_st] = {}
                
                if i == len(target) - 1:
                    transitions[current_st][bad_char] = "q_dead"
                else:
                    transitions[current_st][bad_char] = chain_states[i+1]
                
                for char in alphabet:
                    if char != bad_char:
                        transitions[current_st][char] = safe_state

        # --- SPECIAL HANDLER: CONTAINS CHAIN ---
        elif type_str == "CONTAINS" and target:
            print(f"   [Auto-Repair] Rebuilding Chain for CONTAINS '{target}'")
            
            chain_states = [start_state]
            for i in range(len(target)):
                st_name = f"q{i+1}"
                if st_name not in clean_states: clean_states.append(st_name)
                chain_states.append(st_name)
            
            final_state = chain_states[-1]
            accept_states = {final_state}
            
            for i, current_st in enumerate(chain_states[:-1]):
                match_char = target[i]
                next_st = chain_states[i+1]
                
                transitions[current_st] = {}
                transitions[current_st][match_char] = next_st
                
                for char in alphabet:
                    if char != match_char:
                        transitions[current_st][char] = start_state

            if final_state not in transitions: transitions[final_state] = {}
            transitions[final_state] = {s: final_state for s in alphabet}

        # --- SPECIAL HANDLER: ENDS_WITH & NOT_ENDS_WITH ---
        elif (type_str == "ENDS_WITH" or type_str == "NOT_ENDS_WITH") and target:
            print(f"   [Auto-Repair] Rebuilding Suffix Automaton for {type_str} '{target}'")
            
            # 1. Create states q0..qN (where N = len(target))
            chain_states = [start_state]
            for i in range(len(target)):
                st_name = f"q{i+1}"
                if st_name not in clean_states: clean_states.append(st_name)
                chain_states.append(st_name)
            
            # 2. Determine Transitions (KMP/Suffix Logic)
            for i, current_st in enumerate(chain_states):
                current_prefix = target[:i]
                if current_st not in transitions: transitions[current_st] = {}
                
                for char in alphabet:
                    # Calculate next state: longest prefix of target that is suffix of (current_prefix + char)
                    candidate = current_prefix + char
                    # Trim candidate until it matches a prefix of target
                    while len(candidate) > 0 and not target.startswith(candidate):
                        candidate = candidate[1:]
                    
                    next_index = len(candidate)
                    next_st_name = chain_states[next_index]
                    transitions[current_st][char] = next_st_name

            # 3. Set Accept States
            if type_str == "ENDS_WITH":
                # Only the final state is accept
                accept_states = {chain_states[-1]}
            else:
                # NOT_ENDS_WITH: All states EXCEPT the final one are accept
                accept_states = set(chain_states[:-1])

        # --- GENERAL REPAIR (FALLBACK) ---
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

        # --- PHASE 4: CLEANUP ---
        reachable = {start_state}
        queue = [start_state]
        
        while queue:
            curr = queue.pop(0)
            if curr in transitions:
                for next_st in transitions[curr].values():
                    if next_st not in reachable:
                        reachable.add(next_st)
                        queue.append(next_st)
        
        clean_states = [s for s in clean_states if s in reachable]
        final_accept = [s for s in accept_states if s in reachable]
        
        final_transitions = {}
        for s in clean_states:
            if s in transitions:
                final_transitions[s] = transitions[s]

        data['states'] = sorted(clean_states)
        data['transitions'] = final_transitions
        data['start_state'] = start_state
        data['accept_states'] = sorted(final_accept)
        return DFA(**data)

    # --- HELPER: LOGIC INVERTER ---
    def _try_inversion_fix(self, dfa: DFA, spec: LogicSpec) -> Optional[DFA]:
        all_states = set(dfa.states)
        current_accept = set(dfa.accept_states)
        new_accept = list(all_states - current_accept)
        
        inverted_dfa = DFA(
            states=dfa.states,
            alphabet=dfa.alphabet,
            transitions=dfa.transitions,
            start_state=dfa.start_state,
            accept_states=new_accept,
            reasoning=dfa.reasoning + " (Auto-Inverted by System)"
        )
        
        print("   [System] Checking Inverted Logic...")
        is_valid, _ = self.validator.validate(inverted_dfa, spec)
        
        if is_valid:
            return inverted_dfa
        return None

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
        start_time = time.time()  # <--- TIMER START
        
        spec = self.agent_1_analyst(user_query)
        feedback = ""
        
        for i in range(self.max_retries):
            dfa_obj = self.agent_2_architect(spec, feedback)
            is_valid, error_msg = self.validator.validate(dfa_obj, spec)
            
            if is_valid:
                self.visualizer_tool(dfa_obj)
                
                # --- TIMER END (Success) ---
                end_time = time.time()
                elapsed = end_time - start_time
                print("\n--- SUCCESS ---")
                print(f"[Performance] Task completed in {elapsed:.4f} seconds.")
                return
            
            print("   [System] Validation Failed. Attempting Logic Inversion...")
            inverted_dfa = self._try_inversion_fix(dfa_obj, spec)
            
            if inverted_dfa:
                print("\n   [Auto-Repair] INVERSION TRIGGERED: Swapping Accept/Reject states fixed the logic!")
                self.visualizer_tool(inverted_dfa)
                
                # --- TIMER END (Inversion Success) ---
                end_time = time.time()
                elapsed = end_time - start_time
                print("\n--- SUCCESS (Via Inversion) ---")
                print(f"[Performance] Task completed in {elapsed:.4f} seconds.")
                return

            feedback = error_msg
            print(f">>> Retry {i+1}/{self.max_retries}...")
        
        # --- TIMER END (Failure) ---
        end_time = time.time()
        elapsed = end_time - start_time
        print("\n--- FAILED ---")
        print(f"[Performance] Task failed after {elapsed:.4f} seconds.")

if __name__ == "__main__":
    system = DFAGeneratorSystem()
    
    # --- Batch Challenge Suite ---
    queries = [
        "Design a DFA that accepts strings starting with 'b'",
        "Design a DFA that accepts strings starting with 'bb'",
        "Design a DFA that accepts strings not starting with 'bb'",
        "Design a DFA that accepts strings ending with 'ab'",
        "Design a DFA that accepts strings not ending with 'a'",
        "Design a DFA that accepts strings that contains 'b'",
        "Design a DFA that accepts strings that does not contain 'aa'"
    ]

    print(f"Starting Batch Execution of {len(queries)} challenges...\n")

    for i, query in enumerate(queries, 1):
        print(f"\n{'='*50}")
        print(f"TEST CASE {i}: {query}")
        print(f"{'='*50}")
        
        try:
            system.run(query)
        except Exception as e:
            print(f"!!! CRASH IN TEST {i}: {e}")
            
    print("\n=== Batch Execution Complete ===")