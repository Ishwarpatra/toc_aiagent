// frontend/src/App.jsx - Professional DFA Editor
import { useState } from "react";
import Canvas from "./components/Canvas";
import "./App.css";

// Example prompts for quick selection
const EXAMPLE_PROMPTS = [
  "ends with 'a'",
  "contains '01'",
  "starts with 'ab'",
  "even number of 1s",
  "divisible by 3",
];

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
      const response = await fetch("http://localhost:8000/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail?.error || "Backend connection failed");
      }

      const data = await response.json();
      setDfaData(data);
    } catch (err) {
      console.error(err);
      setError(err.message || "Error: Ensure the Python API is running on port 8000.");
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

        {/* Main Canvas - No bottom bar anymore */}
        <Canvas data={dfaData} loading={loading} error={error} />
      </div>
    </div>
  );
}