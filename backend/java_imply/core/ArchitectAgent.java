package tocaiagent.core;

import java.util.*;

public class ArchitectAgent extends BaseAgent {
    private DFARepairEngine repairEngine;
    public ArchitectAgent(String modelName) { super(modelName); this.repairEngine = new DFARepairEngine(); }

    public DFA design(LogicSpec spec, String feedback) throws Exception {
        System.out.println("\n[Agent 2] Designing DFA... (Feedback: " + (feedback == null || feedback.isEmpty() ? "None" : feedback) + ")");
        // In Python this would call the LLM to generate a JSON DFA.
        // Here we emulate by creating a minimal data map and letting the repair engine fill it.
        Map<String,Object> data = new HashMap<>();
        data.put("states", Arrays.asList("q0"));
        data.put("transitions", new HashMap<>());
        data.put("start_state", "q0");
        data.put("accept_states", new ArrayList<>());
        return repairEngine.autoRepairDfa(data, spec);
    }
}
