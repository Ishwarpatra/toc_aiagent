import Toolbar from "./components/Toolbar";
import Canvas from "./components/Canvas";

export default function App() {
  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#ffffff",
      }}
    >
      {/* Main Area */}
      <div
        style={{
          flex: 1,
          display: "flex",
          background: "#ffffff",
        }}
      >
        <Toolbar />
        <Canvas />
      </div>

      {/* Bottom Play Bar */}
      <div
        style={{
          height: "60px",
          background: "#222",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <button
          style={{
            padding: "10px 24px",
            fontSize: "16px",
            cursor: "pointer",
            border: "none",
            borderRadius: "4px",
          }}
        >
          ▶ Play
        </button>
      </div>
    </div>
  );
}
