import streamlit as st
from main import DFAGeneratorSystem
import graphviz

st.title("🤖 AI Agent: Theory of Computation Teacher")

query = st.text_input("Describe the DFA you want:", "Strings ending in 'ab'")

if st.button("Generate DFA"):
    with st.spinner("Agents are working..."):
        # Initialize System
        system = DFAGeneratorSystem()
        
        # 1. Analyst Agent
        st.subheader("1. Formal Analysis")
        req = system.agent_1_analyst(query)
        st.code(req, language="text")
        
        # 2. Architect & Validator Loop
        dfa_obj = None
        feedback = ""
        
        for i in range(system.max_retries):
            try:
                # Generate
                dfa_obj = system.agent_2_architect(req, feedback)
                
                # Validate
                is_valid, error_msg = system.agent_3_validator(dfa_obj, req)
                
                if is_valid:
                    st.success(f"✅ Logic Verified on Attempt {i+1}")
                    break
                else:
                    st.warning(f"⚠️ Attempt {i+1} Failed: {error_msg}")
                    feedback = error_msg
            except Exception as e:
                st.error(f"Error: {e}")

        # 3. Visualize
        if dfa_obj:
            st.subheader("Final DFA Visualization")
            
            # Recreate Graphviz object for Streamlit
            dot = graphviz.Digraph()
            dot.attr(rankdir='LR')
            
            dot.node('', '', shape='none')
            dot.edge('', dfa_obj.start_state)
            
            for state in dfa_obj.states:
                shape = 'doublecircle' if state in dfa_obj.accept_states else 'circle'
                dot.node(state, state, shape=shape)
                
            for src, trans in dfa_obj.transitions.items():
                for sym, dest in trans.items():
                    dot.edge(src, dest, label=sym)
            
            st.graphviz_chart(dot)