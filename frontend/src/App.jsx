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
          height: "50px",
          background: "#222",
          color: "white",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        ▶ Play
      </div>
    </div>
  );
}
