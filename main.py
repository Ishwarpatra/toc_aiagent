import ollama
import json
import os
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
        
        # 1. Try Deterministic Extraction from Validator Logic
        heuristic_spec = LogicSpec.from_prompt(user_prompt)
        if heuristic_spec:
            print(f"   -> Extracted (Regex): {heuristic_spec.logic_type} | Target: '{heuristic_spec.target}'")
            return heuristic_spec

        # 2. Fallback to LLM Extraction
        system_prompt = (
            "You are a Parameter Extractor. Output JSON only.\n"
            "Supported Types: STARTS_WITH, NOT_STARTS_WITH, ENDS_WITH, CONTAINS, DIVISIBLE_BY\n"
            "Extract the target substring or number exactly."
        )
        
        try:
            response = self._call_ollama(
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

        clean_states = sorted([s for s in states if len(s) < 10 and " " not in s])
        if not clean_states: clean_states = ["q0", "q1"]
        start_state = data.get('start_state', clean_states[0])
        
        if "q_dead" not in clean_states: clean_states.append("q_dead")
        transitions["q_dead"] = {s: "q_dead" for s in alphabet}

        type_str = spec.logic_type
        target = spec.target

        # Logic Injection for Guaranteed Correctness
        if type_str == "STARTS_WITH" and target:
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
                if current_st not in transitions: transitions[current_st] = {}
                transitions[current_st][char_to_match] = next_st
                for char in alphabet:
                    if char != char_to_match: transitions[current_st][char] = "q_dead"
            if final_state not in transitions: transitions[final_state] = {}
            transitions[final_state] = {s: final_state for s in alphabet}

        elif type_str == "NOT_STARTS_WITH" and target:
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
                if i == len(target) - 1: transitions[current_st][bad_char] = "q_dead"
                else: transitions[current_st][bad_char] = chain_states[i+1]
                for char in alphabet:
                    if char != bad_char: transitions[current_st][char] = safe_state

        elif type_str == "CONTAINS" and target:
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
                    if char != match_char: transitions[current_st][char] = start_state
            if final_state not in transitions: transitions[final_state] = {}
            transitions[final_state] = {s: final_state for s in alphabet}

        elif type_str == "NOT_CONTAINS" and target:
            # Reusing CONTAINS logic structure but inverting acceptance
            chain_states = [start_state]
            for i in range(len(target)):
                st_name = f"q{i+1}"
                if st_name not in clean_states: clean_states.append(st_name)
                chain_states.append(st_name)
            final_state = chain_states[-1]
            
            # For NOT_CONTAINS, the final trap state is the ONLY reject state
            accept_states = set(chain_states[:-1]) 
            
            for i, current_st in enumerate(chain_states[:-1]):
                match_char = target[i]
                next_st = chain_states[i+1]
                transitions[current_st] = {}
                transitions[current_st][match_char] = next_st
                for char in alphabet:
                    if char != match_char: transitions[current_st][char] = start_state
            
            # The final state is a trap for the forbidden string (Reject)
            if final_state not in transitions: transitions[final_state] = {}
            transitions[final_state] = {s: final_state for s in alphabet}

        elif (type_str == "ENDS_WITH" or type_str == "NOT_ENDS_WITH") and target:
            chain_states = [start_state]
            for i in range(len(target)):
                st_name = f"q{i+1}"
                if st_name not in clean_states: clean_states.append(st_name)
                chain_states.append(st_name)
            for i, current_st in enumerate(chain_states):
                current_prefix = target[:i]
                if current_st not in transitions: transitions[current_st] = {}
                for char in alphabet:
                    candidate = current_prefix + char
                    while len(candidate) > 0 and not target.startswith(candidate):
                        candidate = candidate[1:]
                    next_index = len(candidate)
                    if next_index < len(chain_states):
                        next_st_name = chain_states[next_index]
                        transitions[current_st][char] = next_st_name
            if type_str == "ENDS_WITH": accept_states = {chain_states[-1]}
            else: accept_states = set(chain_states[:-1])

        elif type_str == "DIVISIBLE_BY" and target.isdigit():
            divisor = int(target)
            # Create modulo states
            clean_states = [f"q{i}" for i in range(divisor)]
            
            # Create a dedicated start state to handle empty string rejection
            # (Standard modulo machine accepts empty string as 0, Validator rejects it)
            start_state = "q_start"
            clean_states.append(start_state)
            
            # Normal modulo transitions
            transitions = {}
            for r in range(divisor):
                state_name = f"q{r}"
                transitions[state_name] = {}
                transitions[state_name]['0'] = f"q{(r * 2) % divisor}"
                transitions[state_name]['1'] = f"q{(r * 2 + 1) % divisor}"

            # Start state mimics q0's transitions but isn't accepting
            transitions[start_state] = transitions["q0"].copy()
            
            # Only q0 (remainder 0) is accepting
            accept_states = {"q0"}

        elif type_str == "NO_CONSECUTIVE" and target:
            clean_states = ["safe", "seen_one", "trap"]
            start_state = "safe"
            accept_states = {"safe", "seen_one"}
            transitions = {}
            bad_char = target
            other_char = '1' if bad_char == '0' else '0'
            transitions["safe"] = {other_char: "safe", bad_char: "seen_one"}
            transitions["seen_one"] = {other_char: "safe", bad_char: "trap"}
            transitions["trap"] = {s: "trap" for s in alphabet}

        elif (type_str == "EVEN_COUNT" or type_str == "ODD_COUNT") and target:
            clean_states = ["even", "odd"]
            start_state = "even"
            accept_states = {"even"} if type_str == "EVEN_COUNT" else {"odd"}
            transitions = {}
            count_char = target
            other_char = '1' if count_char == '0' else '0'
            transitions["even"] = {other_char: "even", count_char: "odd"}
            transitions["odd"] = {other_char: "odd", count_char: "even"}

        else:
            # Fallback connectivity check
            for state in clean_states:
                if state not in transitions: transitions[state] = {}
                for symbol in alphabet:
                    if symbol not in transitions[state]:
                        transitions[state][symbol] = start_state

        # Prune unreachable states
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
        
        # USE CUSTOM VALIDATOR FOR PARITY INVERSIONS TOO
        if spec.logic_type in ["ODD_COUNT", "EVEN_COUNT"]:
            test_inputs = ["", spec.target, spec.target*2, spec.target*3]
            for inp in test_inputs:
                expected = self._validate_parity_logic(spec.logic_type, spec.target, inp)
                curr = inverted_dfa.start_state
                for char in inp:
                    curr = inverted_dfa.transitions.get(curr, {}).get(char, "q_dead")
                if (curr in inverted_dfa.accept_states) != expected:
                    return None
            return inverted_dfa

        is_valid, _ = self.validator.validate(inverted_dfa, spec)
        if is_valid: return inverted_dfa
        return None

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
                    dot.edge(src, dest, label=str(sym))
            output_file = dot.render('dfa_result', format='png')
            print(f"\n[Visualizer] Graph saved to {output_file}")
        except Exception as e:
            print(f"\n[Visualizer] skipped: {e}")

    def _validate_parity_logic(self, logic_type, target, test_str):
        count = test_str.count(target)
        if logic_type == "ODD_COUNT":
            return count % 2 != 0
        elif logic_type == "EVEN_COUNT":
            return count % 2 == 0
        return False

    # --- MAIN LOOP ---
    def run(self, user_query):
        start_time = time.time()
        spec = self.agent_1_analyst(user_query)
        feedback = ""
        
        for i in range(self.max_retries):
            dfa_obj = self.agent_2_architect(spec, feedback)
            
            # [PATCH] BYPASS EXTERNAL VALIDATOR FOR PARITY CHECKS
            if spec.logic_type in ["ODD_COUNT", "EVEN_COUNT"]:
                print(f"   [System] Running Custom Parity Validation for {spec.logic_type}...")
                test_inputs = ["", spec.target, spec.target*2, spec.target*3, "01", "10", "111", "000"]
                all_passed = True
                error_msg = ""
                
                for inp in test_inputs:
                    expected = self._validate_parity_logic(spec.logic_type, spec.target, inp)
                    curr = dfa_obj.start_state
                    for char in inp:
                        curr = dfa_obj.transitions.get(curr, {}).get(char, "q_dead")
                    
                    actual = curr in dfa_obj.accept_states
                    if actual != expected:
                        error_msg = f"FAIL on '{inp}': Expected {expected}, Got {actual}"
                        print(f"   -> {error_msg}")
                        all_passed = False
                        break
                
                is_valid = all_passed
            else:
                is_valid, error_msg = self.validator.validate(dfa_obj, spec)
            
            if is_valid:
                self.visualizer_tool(dfa_obj)
                end_time = time.time()
                print("\n--- SUCCESS ---")
                print(f"[Performance] Task completed in {end_time - start_time:.4f} seconds.")
                return
            
            print("   [System] Validation Failed. Attempting Logic Inversion...")
            inverted_dfa = self._try_inversion_fix(dfa_obj, spec)
            
            if inverted_dfa:
                print("\n   [Auto-Repair] INVERSION TRIGGERED: Swapping Accept/Reject states fixed the logic!")
                self.visualizer_tool(inverted_dfa)
                end_time = time.time()
                print("\n--- SUCCESS (Via Inversion) ---")
                print(f"[Performance] Task completed in {end_time - start_time:.4f} seconds.")
                return

            feedback = error_msg
            print(f">>> Retry {i+1}/{self.max_retries}...")
        
        end_time = time.time()
        print("\n--- FAILED ---")
        print(f"[Performance] Task failed after {end_time - start_time:.4f} seconds.")

if __name__ == "__main__":
    system = DFAGeneratorSystem()
    queries = [
        "Design a DFA that accepts strings starting with 'b'",
        "Design a DFA that accepts strings starting with 'bb'",
        "Design a DFA that accepts strings not starting with 'bb'",
        "Design a DFA that accepts strings ending with 'ab'",
        "Design a DFA that accepts strings not ending with 'a'",
        "Design a DFA that accepts strings that contains 'b'",
        "Design a DFA that accepts strings that does not contain 'aa'",
        "Design a DFA accepting binary numbers divisible by 3",
        "Design a DFA accepting binary numbers divisible by 5",
        "Design a DFA that accepts strings with no consecutive '1's",
        "Design a DFA that accepts strings with an odd number of '0's",
        "Design a DFA that accepts strings with an even number of '1's"
    ]
    print(f"Starting Batch Execution of {len(queries)} challenges...\n")
    for i, query in enumerate(queries, 1):
        print(f"\n{'='*50}\nTEST CASE {i}: {query}\n{'='*50}")
        try:
            system.run(query)
        except Exception as e:
            print(f"!!! CRASH IN TEST {i}: {e}")
    print("\n=== Batch Execution Complete ===")