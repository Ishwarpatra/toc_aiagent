// frontend/src/components/Toolbar.jsx
import { Pencil, Type, Hand, Square } from "lucide-react";

export default function Toolbar({ isMobile }) {
  return (
    <div style={{
      width: isMobile ? "100%" : "60px",
      height: isMobile ? "50px" : "100%",
      background: "#e5e5e5",
      display: "flex",
      flexDirection: isMobile ? "row" : "column", // Change direction for mobile
      alignItems: "center",
      justifyContent: "center",
      gap: isMobile ? "25px" : "12px",
      borderRight: isMobile ? "none" : "1px solid #ccc",
      borderBottom: isMobile ? "1px solid #ccc" : "none"
    }}>
      <Pencil size={20} />
      <Type size={20} />
      <Hand size={20} />
      <Square size={20} />
    </div>
  );
}