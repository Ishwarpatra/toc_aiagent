import { Pencil, Type, Hand, Square } from "lucide-react";

export default function Toolbar() {
  return (
    <div
      style={{
        width: "90px",              // 🔹 increased width
        background: "#e5e5e5",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",       // 🔹 center horizontally
        justifyContent: "center",   // 🔹 center vertically
        gap: "18px",
      }}
    >
      <Pencil size={28} />
      <Type size={28} />
      <Hand size={28} />
      <Square size={28} />
    </div>
  );
}
