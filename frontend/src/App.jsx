// frontend/src/App.jsx
import { useState } from "react";
import Toolbar from "./components/Toolbar";
import Canvas from "./components/Canvas";

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [dfaData, setDfaData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handlePlay = async () => {
    if (!prompt.trim()) return;

    setLoading(true);
    setError(null);

    try {
      // 1. Corrected the variable to 'prompt'
      // 2. Added the missing 'try' block
      const response = await fetch("http://localhost:8000/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt }), 
      });

      if (!response.ok) throw new Error("Backend connection failed");

      const data = await response.json();
      setDfaData(data); 
    } catch (err) {
      console.error(err);
      setError("Error: Ensure the Python API is running on port 8000.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ height: "100vh", width: "100vw", display: "flex", flexDirection: "column", background: "#ffffff", overflow: "hidden" }}>
      
      {/* Question Area (Top Bar) */}
      <div style={{ padding: "10px 20px", borderBottom: "1px solid #ddd", display: "flex", gap: "10px", alignItems: "center", background: "#f8f9fa" }}>
        <span style={{ fontWeight: "bold" }}>Auto-DFA</span>
        <input 
          type="text" 
          placeholder="Describe your DFA (e.g. 'ends with a')" 
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          style={{ flex: 1, padding: "8px", borderRadius: "4px", border: "1px solid #ccc", fontSize: "1rem" }}
        />
      </div>

      {/* Main Workspace */}
      <div style={{ flex: 1, display: "flex", background: "#ffffff", minHeight: 0 }}>
        <Toolbar />
        <Canvas data={dfaData} loading={loading} error={error} />
      </div>

      {/* Generation Button */}
      <div
        onClick={handlePlay}
        style={{
          height: "50px",
          background: loading ? "#555" : "#222",
          color: "white",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: loading ? "wait" : "pointer",
          transition: "background 0.3s"
        }}
      >
        {loading ? "Generating DFA..." : "▶ Play (Generate)"}
      </div>
    </div>
  );
}