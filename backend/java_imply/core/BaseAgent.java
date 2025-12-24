package tocaiagent.core;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class BaseAgent {
    protected String modelName;
    private static final String OLLAMA_API_URL = "http://localhost:11434/api/generate";

    public BaseAgent(String modelName) {
        this.modelName = modelName;
    }

    protected String callOllama(String systemPrompt, String userPrompt) {
        try {
            // Construct JSON payload manually to avoid dependencies
            String escapedSystem = escapeJson(systemPrompt);
            String escapedUser = escapeJson(userPrompt);
            String jsonInputString = String.format(
                "{\"model\": \"%s\", \"prompt\": \"%s\\n%s\", \"stream\": false, \"format\": \"json\"}",
                this.modelName, escapedSystem, escapedUser
            );

            URL url = new URL(OLLAMA_API_URL);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json; utf-8");
            conn.setRequestProperty("Accept", "application/json");
            conn.setDoOutput(true);
            conn.setConnectTimeout(2000); // Fail fast if Ollama isn't running
            conn.setReadTimeout(10000);

            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = jsonInputString.getBytes("utf-8");
                os.write(input, 0, input.length);
            }

            int code = conn.getResponseCode();
            if (code != 200) {
                return null; // Fallback will handle this
            }

            try (BufferedReader br = new BufferedReader(new InputStreamReader(conn.getInputStream(), "utf-8"))) {
                StringBuilder response = new StringBuilder();
                String responseLine;
                while ((responseLine = br.readLine()) != null) {
                    response.append(responseLine.trim());
                }
                return extractResponseField(response.toString());
            }

        } catch (Exception e) {
            // Silently fail and return null to trigger fallback mechanisms
            // System.err.println("LLM Connection Failed: " + e.getMessage());
            return null;
        }
    }

    private String escapeJson(String raw) {
        if (raw == null) return "";
        return raw.replace("\\", "\\\\")
                  .replace("\"", "\\\"")
                  .replace("\n", "\\n")
                  .replace("\r", "");
    }

    private String extractResponseField(String json) {
        // Extract the "response" field from Ollama's output
        // Pattern matches: "response": "..."
        Pattern p = Pattern.compile("\"response\"\\s*:\\s*\"(.*?)\"\\s*,\\s*\"done\"", Pattern.DOTALL);
        Matcher m = p.matcher(json);
        if (m.find()) {
            String content = m.group(1);
            // Unescape common JSON escapes
            return content.replace("\\n", "\n").replace("\\\"", "\"").replace("\\\\", "\\");
        }
        return null;
    }
    
    // Helper to parse simple JSON values without libraries
    protected String extractJsonString(String json, String key) {
        if (json == null) return null;
        Pattern p = Pattern.compile("\"" + key + "\"\\s*:\\s*\"([^\"]+)\"");
        Matcher m = p.matcher(json);
        return m.find() ? m.group(1) : null;
    }
}