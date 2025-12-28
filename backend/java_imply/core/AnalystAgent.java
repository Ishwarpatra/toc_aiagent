package tocaiagent.core;

import java.util.*;

public class AnalystAgent extends BaseAgent {
    public AnalystAgent(String modelName) { super(modelName); }

    public LogicSpec analyze(String userPrompt) {
        System.out.println("\n[Agent 1] Extracting Logic Variables...");

        // 1. Try LLM first
        String systemPrompt = "You are a Theory of Computation expert. Extract logic type, target, and alphabet from the user query. " +
                "Valid types: STARTS_WITH, ENDS_WITH, CONTAINS, NOT_CONTAINS, DIVISIBLE_BY, ODD_COUNT, EVEN_COUNT, NO_CONSECUTIVE. " +
                "Output JSON format: { \"logicType\": \"...\", \"target\": \"...\", \"alphabet\": \"0,1\" }";
        
        String jsonResponse = callOllama(systemPrompt, userPrompt);
        
        if (jsonResponse != null) {
            String type = extractJsonString(jsonResponse, "logicType");
            String target = extractJsonString(jsonResponse, "target");
            String alphaStr = extractJsonString(jsonResponse, "alphabet"); // Primitive parsing
            
            if (type != null) {
                List<String> alphabet = Arrays.asList("0", "1");
                if (alphaStr != null && alphaStr.contains("a")) alphabet = Arrays.asList("a", "b");
                
                System.out.println("   -> [AI] Analyzed: " + type + " '" + target + "'");
                return new LogicSpec(type, target, alphabet);
            }
        }

        // 2. Fallback to Regex Heuristic
        Optional<LogicSpec> heuristic = LogicSpec.fromPrompt(userPrompt);
        if (heuristic.isPresent()) {
            LogicSpec s = heuristic.get();
            System.out.println("   -> [Fallback] Extracted (Regex): " + s.logicType + " | Target: '" + s.target + "'");
            return s;
        }

        // 3. Absolute default
        System.out.println("   -> [Default] Falling back to default LogicSpec CONTAINS '1'");
        return new LogicSpec("CONTAINS", "1", Arrays.asList("0","1"));
    }
}