import { Pencil, Type, Hand, Square } from "lucide-react";

export default function Toolbar() {
  return (
    <div style={{
      width: "60px",
      background: "#e5e5e5",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      paddingTop: "10px",
      gap: "12px"
    }}>
      <Pencil />
      <Type />
      <Hand />
      <Square />
    </div>
  );
}
