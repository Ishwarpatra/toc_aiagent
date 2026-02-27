// frontend/src/App.jsx - Professional DFA Editor
import { useState } from "react";
import Canvas from "./components/Canvas";
import ErrorBoundary from "./components/ErrorBoundary";
import "./App.css";

// API URL from environment variable with fallback to localhost for development
// Empty string means use relative paths (for nginx proxy in production)
const API_URL = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? "" : "http://localhost:8000");

// Example prompts for quick selection
const EXAMPLE_PROMPTS = [
  "ends with 'a'",
  "contains '01'",
  "starts with 'ab'",
  "even number of 1s",
  "divisible by 3",
];

/**
 * Parse error response and return appropriate user-friendly message
 */
const parseErrorResponse = (errorData, statusCode) => {
  const detail = errorData?.detail;

  if (typeof detail === "object" && detail !== null) {
    const errorType = detail.error_type || "Unknown";
    const errorMsg = detail.error || "An error occurred";
    const hint = detail.hint || "";

    // Format based on error type
    switch (errorType) {
      case "ServiceUnavailable":
        return `Service unavailable: ${errorMsg}${hint ? ` (${hint})` : ""}`;
      case "ValidationError":
        return `Invalid request: ${errorMsg}${hint ? `. Hint: ${hint}` : ""}`;
      case "ConnectionError":
        return `Connection failed: ${errorMsg}`;
      default:
        return `${errorMsg}${hint ? ` - ${hint}` : ""}`;
    }
  }

  // Handle string detail or fallback
  if (typeof detail === "string") {
    return detail;
  }

  // Default messages based on status code
  switch (statusCode) {
    case 503:
      return "Service unavailable. Is the Ollama AI service running?";
    case 400:
      return "Invalid request. Check your prompt format.";
    case 500:
      return "Internal server error. Please try again later.";
    default:
      return "Backend connection failed";
  }
};

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [dfaData, setDfaData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleGenerate = async () => {
    if (!prompt.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(parseErrorResponse(errorData, response.status));
      }

      const data = await response.json();
      setDfaData(data);
    } catch (err) {
      console.error(err);
      // Check if it's a network error (fetch failed entirely)
      if (err.name === "TypeError" && err.message.includes("fetch")) {
        setError(`Cannot connect to API at ${API_URL}. Ensure the backend is running.`);
      } else {
        setError(err.message || "Error: Ensure the Python API is running.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleExampleClick = (example) => {
    setPrompt(example);
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && e.ctrlKey) {
      handleGenerate();
    }
  };

  return (
    <div className="app-container">
      <div className="main-workspace">
        {/* Left Sidebar - Question Input */}
        <aside className="sidebar">
          <div className="sidebar-header">
            <div className="sidebar-logo">
              <span className="sidebar-logo-icon">◊</span>
              Auto-DFA
            </div>
            <div className="sidebar-subtitle">AI-Powered State Machine Generator</div>
          </div>

          <div className="sidebar-content">
            {/* Prompt Input */}
            <div className="prompt-section">
              <label className="section-label">Describe Your DFA</label>
              <textarea
                className="prompt-textarea"
                placeholder="Enter a natural language description...

Examples:
• Strings ending with 'a'
• Contains substring '01'
• Even number of 1s
• Divisible by 3"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={handleKeyPress}
              />

              <button
                className="generate-btn"
                onClick={handleGenerate}
                disabled={loading || !prompt.trim()}
              >
                {loading ? (
                  <>
                    <span className="generate-btn-icon">⟳</span>
                    Generating...
                  </>
                ) : (
                  <>
                    <span className="generate-btn-icon">⚡</span>
                    Generate DFA
                  </>
                )}
              </button>
            </div>

            {/* Quick Examples */}
            <div className="examples-section">
              <label className="section-label">Quick Examples</label>
              <div className="examples-list">
                {EXAMPLE_PROMPTS.map((example, index) => (
                  <button
                    key={index}
                    className="example-chip"
                    onClick={() => handleExampleClick(example)}
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </aside>

        {/* Main Canvas - wrapped in ErrorBoundary */}
        <ErrorBoundary>
          <Canvas data={dfaData} loading={loading} error={error} />
        </ErrorBoundary>
      </div>
    </div>
  );
}