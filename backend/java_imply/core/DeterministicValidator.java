package tocaiagent.core;

import java.util.*;

public class DeterministicValidator {
    public ValidationResult validate(DFA dfa, LogicSpec spec) {
        System.out.println("\n[Validator] Running Checks for " + spec.logicType + " '" + spec.target + "'...");
        
        // Dynamic test input generation
        List<String> testInputs = new ArrayList<>(Arrays.asList("", "0", "1", "00", "01", "10", "11"));
        if (spec.alphabet.contains("a")) {
             testInputs.addAll(Arrays.asList("a", "b", "aa", "ab", "ba", "bb"));
        }
        
        if (spec.target != null && !spec.target.isEmpty()) {
            String t = spec.target;
            testInputs.add(t);
            testInputs.add(t + spec.alphabet.get(0));
            testInputs.add(spec.alphabet.get(1) + t);
        }
        
        // Deduplicate
        Set<String> uniq = new HashSet<>(testInputs);
        List<String> finalInputs = new ArrayList<>(uniq);
        List<String> errorLog = new ArrayList<>();

        for (String s : finalInputs) {
            // Skip strings containing symbols not in alphabet
            boolean skip = false;
            for (char c : s.toCharArray()) {
                if (!spec.alphabet.contains(String.valueOf(c))) { skip = true; break; }
            }
            if (skip) continue;

            boolean expected = getTruth(s, spec);
            boolean actual;
            try {
                actual = _simulate_dfa(dfa, s);
            } catch (Exception e) {
                return new ValidationResult(false, "Simulation Crashed: " + e.getMessage());
            }
            
            if (expected != actual) {
                String verdict = actual ? "ACCEPTED" : "REJECTED";
                String shouldBe = expected ? "ACCEPT" : "REJECT";
                errorLog.add(String.format("FAIL: Input '%s' was %s (Expected %s)", s, verdict, shouldBe));
            }
        }

        if (errorLog.isEmpty()) {
            System.out.println("   -> ALL TESTS PASSED.");
            return new ValidationResult(true, "Passed");
        } else {
            String feedback = String.join("\n", errorLog.subList(0, Math.min(3, errorLog.size())));
            System.out.println("   -> FAILURES FOUND:\n" + feedback);
            return new ValidationResult(false, feedback);
        }
    }

    public boolean getTruth(String s, LogicSpec spec) {
        String t = spec.target;
        String lt = spec.logicType;
        if (s == null) return false;

        if ("STARTS_WITH".equals(lt)) return s.startsWith(t);
        if ("NOT_STARTS_WITH".equals(lt)) return !s.startsWith(t);
        if ("ENDS_WITH".equals(lt)) return s.endsWith(t);
        if ("NOT_ENDS_WITH".equals(lt)) return !s.endsWith(t);
        if ("CONTAINS".equals(lt)) return s.contains(t);
        if ("NOT_CONTAINS".equals(lt)) return !s.contains(t);
        if ("NO_CONSECUTIVE".equals(lt)) return !s.contains(t + t);
        
        if ("DIVISIBLE_BY".equals(lt)) {
            if (s.isEmpty()) return false;
            try {
                // Heuristic: determine base
                int radix = 10;
                boolean isBinary = true;
                for(char c : s.toCharArray()) if(c!='0' && c!='1') isBinary = false;
                
                if (isBinary && spec.alphabet.contains("0")) radix = 2;
                
                // If inputs are 'a','b', we cannot mathematically divide them unless mapped
                if (!isBinary) return false; 

                long num = Long.parseLong(s, radix);
                long div = Long.parseLong(t);
                return num % div == 0;
            } catch (Exception e) { return false; }
        }
        
        if ("ODD_COUNT".equals(lt)) return (countOccurrences(s, t) % 2 != 0);
        if ("EVEN_COUNT".equals(lt)) return (countOccurrences(s, t) % 2 == 0);
        
        return false;
    }
    
    private int countOccurrences(String str, String target) {
        if (target.isEmpty()) return 0;
        return (str.length() - str.replace(target, "").length()) / target.length();
    }

    private boolean _simulate_dfa(DFA dfa, String s) {
        String current = dfa.startState;
        if (current == null) return false;
        
        for (char c : s.toCharArray()) {
            if (dfa.transitions == null || !dfa.transitions.containsKey(current)) return false;
            String ch = String.valueOf(c);
            Map<String,String> map = dfa.transitions.get(current);
            if (map == null || !map.containsKey(ch)) return false; // Implicit reject (trap)
            current = map.get(ch);
        }
        return dfa.acceptStates.contains(current);
    }
}