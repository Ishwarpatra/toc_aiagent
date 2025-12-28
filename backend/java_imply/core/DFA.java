package tocaiagent.core;

import java.util.*;

public class DFA {
    public String reasoning = "";
    public List<String> states;
    public List<String> alphabet;
    public Map<String, Map<String, String>> transitions;
    public String startState;
    public List<String> acceptStates;

    public DFA(List<String> states,
               List<String> alphabet,
               Map<String, Map<String, String>> transitions,
               String startState,
               List<String> acceptStates,
               String reasoning) {
        this.states = states != null ? states : new ArrayList<>();
        this.alphabet = alphabet != null ? alphabet : Arrays.asList("0", "1");
        this.transitions = transitions != null ? transitions : new HashMap<>();
        this.startState = startState;
        this.acceptStates = acceptStates != null ? acceptStates : new ArrayList<>();
        if (reasoning != null) this.reasoning = reasoning;
        validateIntegrity();
    }

    private void validateIntegrity() {
        if (this.startState != null && !this.states.contains(this.startState)) {
            // allow repair later; don't throw
        }
    }
}
