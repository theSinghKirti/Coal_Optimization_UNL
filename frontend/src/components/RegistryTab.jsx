import React from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, LabelList,
  PieChart, Pie, Cell, Legend, ResponsiveContainer
} from "recharts";
import {
  mt, shortPlant, COLORS
} from "../lib/utils";

export default function RegistryTab({ constraints }) {
  return (
    <div className="page-content" id="tab-registry">
      <p className="section-intro">
        Parsed deterministically from the FSA and Bridge Linkage matrix (2026-27). Prose FSAs and orders
        go through Claude extraction into this same registry with a "pending" status until approved.
      </p>

      {/* ACQ breakdown chart */}
      <div className="charts-row">
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title-graphics">ACQ Distribution (Lac MT / yr)</span>
            <span className="panel-badge amber">FSA + Bridge</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={Object.values(
                constraints.reduce((acc, r) => {
                  const sName = shortPlant(r.plant);
                  if (!acc[sName]) acc[sName] = { plant: sName, fsa: 0, bridge: 0 };
                  if (r.linkage_type === "FSA") acc[sName].fsa += r.acq_lac_mt;
                  else acc[sName].bridge += r.acq_lac_mt;
                  return acc;
                }, {})
              )}
              margin={{ top: 25, right: 8, left: -12, bottom: 0 }}
            >
              <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="plant" tick={{ fill: "#8892a4", fontSize: 10 }} textAnchor="middle" axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#8892a4", fontSize: 10 }} axisLine={false} tickLine={false} />
              <Bar dataKey="fsa" name="FSA (Lac MT)" fill={COLORS.teal} radius={[4, 4, 0, 0]}>
                <LabelList dataKey="fsa" position="top" formatter={(v) => v > 0 ? v.toFixed(1) : ""} style={{ fill: COLORS.teal, fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
              </Bar>
              <Bar dataKey="bridge" name="Bridge Linkage (Lac MT)" fill={COLORS.amber} radius={[4, 4, 0, 0]}>
                <LabelList dataKey="bridge" position="top" formatter={(v) => v > 0 ? v.toFixed(1) : ""} style={{ fill: COLORS.amber, fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span className="panel-title-graphics">FSA vs Bridge Split</span>
            <span className="panel-badge violet">Breakdown</span>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={[
                  { name: "FSA", value: parseFloat(constraints.filter((r) => r.linkage_type === "FSA").reduce((s, r) => s + r.acq_lac_mt, 0).toFixed(2)) },
                  { name: "Bridge Linkage", value: parseFloat(constraints.filter((r) => r.linkage_type !== "FSA").reduce((s, r) => s + r.acq_lac_mt, 0).toFixed(2)) },
                ]}
                cx="50%"
                cy="46%"
                innerRadius={45}
                outerRadius={75}
                paddingAngle={4}
                dataKey="value"
                nameKey="name"
                label={({ payload, percent }) =>
                  `${payload.name}: ${payload.value.toFixed(1)} (${(percent*100).toFixed(0)}%)`
                }
                labelLine={{ stroke: "#94a3b8", strokeWidth: 1 }}
              >
                <Cell fill={COLORS.teal} stroke="transparent" />
                <Cell fill={COLORS.amber} stroke="transparent" />
              </Pie>
              <Legend formatter={(v) => <span style={{ color: "#8892a4", fontSize: 11, fontFamily: "var(--font-mono)" }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Constraint Registry</span>
          <span className="panel-badge teal">{constraints.length} entries</span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Plant</th>
              <th>Company</th>
              <th>Type</th>
              <th>ACQ (Lac MT / yr)</th>
              <th>Monthly Cap (MT)</th>
              <th>Valid To</th>
            </tr>
          </thead>
          <tbody>
            {constraints.map((r, i) => (
              <tr key={i}>
                <td className="cell-plant">{r.plant}</td>
                <td style={{ color: "var(--ink)" }}>{r.company}</td>
                <td>
                  <span className={`tag ${r.linkage_type === "FSA" ? "tag-fsa" : "tag-bridge"}`}>
                    {r.linkage_type === "FSA" ? "FSA" : "Bridge"}
                  </span>
                </td>
                <td>{r.acq_lac_mt.toFixed(2)}</td>
                <td>{mt((r.acq_lac_mt * 100000) / 12)}</td>
                <td style={{ color: r.valid_to ? COLORS.amber : "var(--ink-dim)" }}>
                  {r.valid_to || "Perpetual"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
