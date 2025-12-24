package tocaiagent.core;

import java.util.*;
import java.util.stream.Collectors;

public class DFARepairEngine {
    
    public DFA autoRepairDfa(Map<String,Object> data, LogicSpec spec) {
        Set<String> states = new HashSet<>();
        Object stObj = data.get("states");
        if (stObj instanceof List) {
            for (Object o : (List<?>)stObj) states.add(String.valueOf(o));
        }
        
        @SuppressWarnings("unchecked")
        Map<String, Map<String, String>> transitions = (Map<String, Map<String, String>>) data.getOrDefault("transitions", new HashMap<>());
        List<String> alphabet = spec.alphabet;
        Set<String> acceptStates = new HashSet<>();
        Object aObj = data.get("accept_states");
        if (aObj instanceof List) for (Object o : (List<?>)aObj) acceptStates.add(String.valueOf(o));

        // 1. Basic Cleanup
        List<String> cleanStates = states.stream().filter(s -> s.length() < 15 && !s.contains(" ")).sorted().collect(Collectors.toList());
        if (cleanStates.isEmpty()) cleanStates = new ArrayList<>(Arrays.asList("q0","q1"));
        
        String startState = data.getOrDefault("start_state", cleanStates.get(0)).toString();
        
        // Ensure dead state exists
        if (!cleanStates.contains("q_dead")) cleanStates.add("q_dead");
        Map<String, String> deadMap = new HashMap<>();
        for (String sym : alphabet) deadMap.put(sym, "q_dead");
        transitions.put("q_dead", deadMap);

        String typeStr = spec.logicType;
        String target = spec.target != null ? spec.target : "";

        // 2. Apply Rule-Based Construction
        boolean needsRebuild = transitions.size() <= 1 || transitions.get(startState) == null || transitions.get(startState).isEmpty();

        if (needsRebuild) {
            cleanStates.clear();
            transitions.clear();
            acceptStates.clear();
            startState = "q0";
            
            // Re-add dead state logic
            transitions.put("q_dead", deadMap); 
            if(!cleanStates.contains("q_dead")) cleanStates.add("q_dead");

            if ("STARTS_WITH".equals(typeStr) && !target.isEmpty()) {
                cleanStates.add("q0");
                List<String> required = new ArrayList<>();
                required.add(startState);
                for (int i=0;i<target.length();i++) {
                    String name = "q" + (i+1);
                    if (!cleanStates.contains(name)) cleanStates.add(name);
                    required.add(name);
                }
                String finalState = required.get(required.size()-1);
                acceptStates.add(finalState);
                
                for (int i=0;i<required.size()-1;i++) {
                    String cur = required.get(i);
                    char match = target.charAt(i);
                    String next = required.get(i+1);
                    transitions.putIfAbsent(cur, new HashMap<>());
                    transitions.get(cur).put(String.valueOf(match), next);
                    for (String c : alphabet) {
                        if (!c.equals(String.valueOf(match))) transitions.get(cur).put(c, "q_dead");
                    }
                }
                transitions.putIfAbsent(finalState, new HashMap<>());
                Map<String,String> finalMap = new HashMap<>();
                for (String s : alphabet) finalMap.put(s, finalState);
                transitions.put(finalState, finalMap);
            }
            
            else if ("ENDS_WITH".equals(typeStr) && !target.isEmpty()) {
                 for (int i=0; i<=target.length(); i++) {
                     String s = "q" + i;
                     if (!cleanStates.contains(s)) cleanStates.add(s);
                 }
                 startState = "q0";
                 acceptStates.add("q" + target.length());
                 
                 for (int i=0; i<=target.length(); i++) {
                     String curState = "q" + i;
                     transitions.putIfAbsent(curState, new HashMap<>());
                     String prefix = target.substring(0, i);
                     
                     for (String charStr : alphabet) {
                         String candidate = prefix + charStr;
                         int matchLen = 0;
                         for (int k = Math.min(candidate.length(), target.length()); k > 0; k--) {
                             if (target.startsWith(candidate.substring(candidate.length() - k))) {
                                 matchLen = k;
                                 break;
                             }
                         }
                         transitions.get(curState).put(charStr, "q" + matchLen);
                     }
                 }
            }

            else if ("CONTAINS".equals(typeStr) && !target.isEmpty()) {
                List<String> chain = new ArrayList<>();
                chain.add("q0");
                if(!cleanStates.contains("q0")) cleanStates.add("q0");
                
                for (int i=0;i<target.length();i++) {
                    String name = "q" + (i+1);
                    if (!cleanStates.contains(name)) cleanStates.add(name);
                    chain.add(name);
                }
                String finalState = chain.get(chain.size()-1);
                acceptStates.add(finalState);
                
                for (int i=0;i<chain.size()-1;i++) {
                    String cur = chain.get(i);
                    char match = target.charAt(i);
                    String next = chain.get(i+1);
                    Map<String,String> curMap = new HashMap<>();
                    curMap.put(String.valueOf(match), next);
                    for (String c : alphabet) {
                        if (!c.equals(String.valueOf(match))) curMap.put(c, startState);
                    }
                    transitions.put(cur, curMap);
                }
                Map<String,String> fm = new HashMap<>();
                for (String s : alphabet) fm.put(s, finalState);
                transitions.put(finalState, fm);
            }
            
            else if ("DIVISIBLE_BY".equals(typeStr)) {
                try {
                    int divisor = Integer.parseInt(target);
                    // Create standard remainder states q0..q(n-1)
                    for (int i=0;i<divisor;i++) {
                        String s = "q" + i;
                        if(!cleanStates.contains(s)) cleanStates.add(s);
                        if (i==0) acceptStates.add(s); // q0 is accept (remainder 0)
                        transitions.put(s, new HashMap<>());
                    }
                    
                    // Logic for remainder states
                    for (int r=0; r<divisor; r++) {
                        String current = "q" + r;
                        int next0 = (r * 2) % divisor;
                        int next1 = (r * 2 + 1) % divisor;
                        transitions.get(current).put("0", "q" + next0);
                        transitions.get(current).put("1", "q" + next1);
                        
                        // Trap non-binary inputs
                        for(String sym : alphabet) {
                            if(!sym.equals("0") && !sym.equals("1")) 
                                transitions.get(current).put(sym, "q_dead");
                        }
                    }

                    // --- FIX FOR EMPTY STRING ---
                    // Create a dedicated start state 'q_start' which is NOT accepting.
                    // This ensures empty string is rejected.
                    // Transitions from q_start immediately mimic q0's transitions logic
                    // because input '0' -> value 0 (rem 0) -> q0, '1' -> value 1 (rem 1) -> q1
                    startState = "q_start";
                    cleanStates.add(startState);
                    Map<String, String> stMap = new HashMap<>();
                    stMap.put("0", "q0");
                    stMap.put("1", "q" + (1 % divisor));
                    for(String sym : alphabet) {
                         if(!sym.equals("0") && !sym.equals("1")) stMap.put(sym, "q_dead");
                    }
                    transitions.put(startState, stMap);
                    
                } catch (Exception e) { /* Fallback */ }
            }
            
            else {
                // Default Fallback
                if(!cleanStates.contains("q0")) cleanStates.add("q0");
                for (String s : cleanStates) {
                    transitions.putIfAbsent(s, new HashMap<>());
                    for (String symbol : alphabet) {
                        transitions.get(s).putIfAbsent(symbol, startState);
                    }
                }
            }
        }

        // 3. Final structural validation
        for (String s : cleanStates) {
            transitions.putIfAbsent(s, new HashMap<>());
            for (String symbol : alphabet) {
                if (!transitions.get(s).containsKey(symbol)) {
                    transitions.get(s).put(symbol, "q_dead");
                }
            }
        }

        return new DFA(cleanStates, alphabet, transitions, startState, new ArrayList<>(acceptStates), (String)data.getOrDefault("reasoning", ""));
    }

    public Optional<DFA> tryInversionFix(DFA dfa, LogicSpec spec, DeterministicValidator validator) {
        Set<String> all = new HashSet<>(dfa.states);
        Set<String> currentAccept = new HashSet<>(dfa.acceptStates);
        List<String> newAccept = all.stream().filter(s -> !currentAccept.contains(s)).collect(Collectors.toList());
        
        DFA inverted = new DFA(dfa.states, dfa.alphabet, dfa.transitions, dfa.startState, newAccept, dfa.reasoning + " (Auto-Inverted by System)");
        ValidationResult res = validator.validate(inverted, spec);
        
        if (res.isValid) return Optional.of(inverted);
        return Optional.empty();
    }
}