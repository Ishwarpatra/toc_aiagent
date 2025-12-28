package tocaiagent.core;

import java.util.*;
import java.util.regex.*;

public class LogicSpec {
    public String logicType;
    public String target;
    public List<String> alphabet;

    public LogicSpec(String logicType, String target, List<String> alphabet) {
        this.logicType = logicType;
        this.target = target;
        this.alphabet = alphabet != null ? alphabet : Arrays.asList("0", "1");
    }

    public static Optional<LogicSpec> fromPrompt(String userPrompt) {
        if (userPrompt == null) return Optional.empty();
        String lower = userPrompt.toLowerCase();
        String deducedType = null;
        String deducedTarget = null;
        List<String> deducedAlphabet = Arrays.asList("0", "1");

        if (Pattern.compile("[a-zA-Z]").matcher(userPrompt).find()) {
            deducedAlphabet = Arrays.asList("a", "b");
        }

        // Parity
        Matcher parity = Pattern.compile("(odd|even)\\s+number\\s+of\\s+['\"]?([01a-zA-Z])['\"]?s?").matcher(lower);
        if (parity.find()) {
            String ptype = parity.group(1);
            String ch = parity.group(2);
            deducedType = ptype.equals("odd") ? "ODD_COUNT" : "EVEN_COUNT";
            deducedTarget = ch;
        }
        // Divisible
        else if (lower.contains("divisible by")) {
            deducedType = "DIVISIBLE_BY";
            Matcher m = Pattern.compile("divisible\\s+by\\s+(\\d+)").matcher(lower);
            if (m.find()) deducedTarget = m.group(1);
        }
        else if (lower.contains("no consecutive")) {
            deducedType = "NO_CONSECUTIVE";
            Matcher m = Pattern.compile("consecutive\\s+['\"]?([01a-zA-Z])['\"]?s?").matcher(lower);
            if (m.find()) deducedTarget = m.group(1); else deducedTarget = "1";
        }
        else if (lower.contains("not start") || lower.contains("does not start")) deducedType = "NOT_STARTS_WITH";
        else if (lower.contains("start") || lower.contains("begin")) deducedType = "STARTS_WITH";
        else if (lower.contains("not end") || lower.contains("does not end")) deducedType = "NOT_ENDS_WITH";
        else if (lower.contains("end")) deducedType = "ENDS_WITH";
        else if (lower.contains("not contain")) deducedType = "NOT_CONTAINS";
        else if (lower.contains("contain")) deducedType = "CONTAINS";

        if (deducedType != null && deducedTarget != null) {
            if (Pattern.compile("[a-zA-Z]").matcher(deducedTarget).find()) {
                deducedAlphabet = Arrays.asList("a", "b");
            }
            return Optional.of(new LogicSpec(deducedType, deducedTarget, deducedAlphabet));
        }
        return Optional.empty();
    }
}
