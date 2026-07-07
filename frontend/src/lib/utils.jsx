import React from "react";

export const inr = (n, short = false) => {
  if (n == null) return "—";
  if (short) {
    if (Math.abs(n) >= 1e7) return "₹" + (n / 1e7).toFixed(1) + " Cr";
    if (Math.abs(n) >= 1e5) return "₹" + (n / 1e5).toFixed(1) + " L";
    return "₹" + Math.round(n).toLocaleString("en-IN");
  }
  return "₹" + new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(n);
};

export const mt = (n) =>
  n == null ? "—" : new Intl.NumberFormat("en-IN").format(Math.round(n)) + " MT";

export const pct = (n) => (n == null ? "—" : n.toFixed(1) + "%");

export const shortPlant = (name) => {
  if (!name) return "";
  const map = {
    "Anpara": "ANPR",
    "Harduaganj": "HRDG",
    "Jawaharpur": "JWHP",
    "Obra B": "OB-B",
    "Obra C": "OB-C",
    "Panki Extn": "PNKI",
    "Parichha": "PRCH",
    "Obra": "OBRA",
    "Harduaganj Extn-II": "HRDG-II"
  };
  return map[name] || name.split(" ")[0].toUpperCase();
};

export const COLORS = {
  amber:  "#d97706",
  teal:   "#0d9488",
  coral:  "#dc2626",
  violet: "#7c3aed",
  sky:    "#0284c7",
  rose:   "#e11d48",
};

export const COMPANY_COLORS = ["#d97706","#0d9488","#7c3aed","#0284c7","#dc2626","#16a34a","#db2777"];

export const CO_COLOR = {
  NCL:  "#0d9488",
  CCL:  "#d97706",
  BCCL: "#7c3aed",
  SECL: "#0284c7",
  ECL:  "#dc2626",
};

export function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="custom-tooltip" style={{ background: "rgba(255,255,255,0.9)", border: "1px solid #ccc", padding: "8px", borderRadius: "4px" }}>
      <div style={{ color: "#0f172a", marginBottom: 6, fontWeight: 700, fontSize: 13 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || "#d97706", marginBottom: 2 }}>
          {p.name}: {typeof p.value === "number" && p.value > 1e4 ? inr(p.value, true) : p.value?.toLocaleString("en-IN") ?? "—"}
        </div>
      ))}
    </div>
  );
}

// IPP benchmarks
export const IPP_VC = 3.90;
export const HEAT_RATE = 2400;
export const BLEND_GCV = 3800;

export const currentAllocations = [
  { plant: "Anpara", company: "NCL", allocated_mt: 988666.7, landed_cost_rs_mt: 2947 },
  { plant: "Harduaganj", company: "CCL", allocated_mt: 204250.0, landed_cost_rs_mt: 4513 },
  { plant: "Harduaganj", company: "BCCL", allocated_mt: 199417.0, landed_cost_rs_mt: 6691 },
  { plant: "Harduaganj", company: "Market", allocated_mt: 0, landed_cost_rs_mt: 7563 },
  { plant: "Jawaharpur", company: "SECL", allocated_mt: 135583.3, landed_cost_rs_mt: 5305 },
  { plant: "Jawaharpur", company: "ECL", allocated_mt: 135583.3, landed_cost_rs_mt: 5087 },
  { plant: "Jawaharpur", company: "BCCL", allocated_mt: 130833.4, landed_cost_rs_mt: 7076 },
  { plant: "Obra B", company: "NCL", allocated_mt: 301333.0, landed_cost_rs_mt: 3049.8 },
  { plant: "Obra C", company: "NCL", allocated_mt: 178000.0, landed_cost_rs_mt: 3595 },
  { plant: "Obra C", company: "BCCL", allocated_mt: 178000.0, landed_cost_rs_mt: 6041 },
  { plant: "Panki Extn", company: "CCL", allocated_mt: 205667.0, landed_cost_rs_mt: 4313 },
  { plant: "Panki Extn", company: "Market", allocated_mt: 0, landed_cost_rs_mt: 5823 },
  { plant: "Parichha", company: "NCL", allocated_mt: 177333.3, landed_cost_rs_mt: 4513 },
  { plant: "Parichha", company: "CCL", allocated_mt: 177333.6, landed_cost_rs_mt: 4308 },
  { plant: "Parichha", company: "Market", allocated_mt: 0, landed_cost_rs_mt: 5954 },
];
