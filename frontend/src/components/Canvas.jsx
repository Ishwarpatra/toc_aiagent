// frontend/src/components/Canvas.jsx
import { useEffect, useRef } from "react";
import mermaid from "mermaid";

mermaid.initialize({ startOnLoad: true });

export default function Canvas({ data, loading, error }) {
  const mermaidRef = useRef(null);

  useEffect(() => {
    if (data?.dfa && mermaidRef.current) {
      const { start_state, accept_states, transitions } = data.dfa;
      
      // Convert JSON DFA to Mermaid stateDiagram syntax
      let chart = "stateDiagram-v2\n  direction LR\n";
      chart += `  [*] --> ${start_state}\n`;

      Object.entries(transitions).forEach(([src, transMap]) => {
        Object.entries(transMap).forEach(([symbol, dest]) => {
          chart += `  ${src} --> ${dest} : ${symbol}\n`;
        });
      });

      accept_states.forEach(state => {
        chart += `  class ${state} accept\n`;
      });
      chart += `  classDef accept fill:#82E0AA,stroke:#333,stroke-width:2px;\n`;

      mermaid.render("graphDiv", chart).then(({ svg }) => {
        mermaidRef.current.innerHTML = svg;
      });
    }
  }, [data]);

  return (
    <div style={{ flex: 1, display: "flex", justifyContent: "center", alignItems: "center" }}>
      {loading && <p>Architecting DFA...</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}
      <div ref={mermaidRef} />
    </div>
  );
}