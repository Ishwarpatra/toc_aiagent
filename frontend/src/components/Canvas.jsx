export default function Canvas() {
  return (
    <div
      style={{
        flex: 1,
        background: "#ffffff",
        padding: "16px",
        display: "flex",
        alignItems: "flex-start",     // 🔹 top
        justifyContent: "flex-start", // 🔹 left
        fontSize: "16px",
        color: "#333",
      }}
    >
      DFA Visualization Area
    </div>
  );
}
