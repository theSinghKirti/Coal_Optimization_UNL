import React, { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, LabelList, Cell, ResponsiveContainer
} from "recharts";
import {
  mt, shortPlant, COLORS, COMPANY_COLORS
} from "../lib/utils";
import LiveFuelPosition from "./LiveFuelPosition";

export default function FuelPositionTab({ daily_fuel, liveData }) {
  
  const stockCoverData = useMemo(() =>
    daily_fuel
      .filter((r) => r.fuel_type === "COAL")
      .map((r) => ({
        plant: shortPlant(r.plant),
        fullPlant: r.plant,
        days: parseFloat(Number(r.days_stock_cover || 0).toFixed(1)),
        closing: r.closing_balance,
        plf: parseFloat(Number(r.plf_pct || 0).toFixed(1)),
        rakes: r.rakes_received || 0,
        gen: r.generation_mu || 0,
      }))
      .sort((a, b) => b.days - a.days),
  [daily_fuel]);


  const reportDate = useMemo(() => {
    return daily_fuel[0]?.report_date || "30 Jun 2026";
  }, [daily_fuel]);

  return (
    <div className="page-content" id="tab-daily">

      {/* ── Phase 1B: Live Backend Data ── */}
      {liveData && <LiveFuelPosition liveData={liveData} />}

      {/* ── Demo snapshot divider ── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          margin: "8px 0 14px",
          padding: "8px 14px",
          background: "rgba(124,58,237,0.06)",
          border: "1.5px solid rgba(124,58,237,0.20)",
          borderRadius: 8,
        }}
      >
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            fontFamily: "var(--font-mono)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "var(--violet)",
            background: "rgba(124,58,237,0.10)",
            border: "1.5px solid rgba(124,58,237,0.25)",
            borderRadius: 20,
            padding: "2px 9px",
          }}
        >
          DEMO DATA
        </span>
        <span style={{ fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-body)" }}>
          Charts and table below are from the demo snapshot, not live backend data.
        </span>
      </div>

      <p className="section-intro">
        Daily coal/fuel position from the WhatsApp-collected report. Reconciliation check:
        opening + receipt − consumption = closing (flagged if Δ &gt; 1 MT).
      </p>

      {/* Summary charts */}
      <div className="charts-row">
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title-graphics">Closing Balance per Plant (MT)</span>
            <span className="panel-badge teal">Today</span>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart
              data={stockCoverData}
              margin={{ top: 25, right: 8, left: -8, bottom: 0 }}
            >
              <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="plant" tick={{ fill: "#8892a4", fontSize: 10 }} textAnchor="middle" axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#8892a4", fontSize: 10 }} axisLine={false} tickLine={false}
                tickFormatter={(v) => (v / 1000).toFixed(0) + "k"} />
              <Bar dataKey="closing" name="Closing MT" fill={COLORS.teal} radius={[4, 4, 0, 0]}>
                <LabelList dataKey="closing" position="top" formatter={(v) => v > 0 ? (v/1000).toFixed(0)+"k" : ""} style={{ fill: COLORS.teal, fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
              </Bar>
              <Bar dataKey="days" name="Days cover" fill={COLORS.amber} radius={[4, 4, 0, 0]}>
                <LabelList dataKey="days" position="top" formatter={(v) => v > 0 ? v.toFixed(1)+"d" : ""} style={{ fill: COLORS.amber, fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span className="panel-title-graphics">Rakes Received Today</span>
            <span className="panel-badge amber">Logistics</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={stockCoverData.filter((r) => r.rakes > 0)}
              margin={{ top: 20, right: 8, left: -20, bottom: 0 }}
            >
              <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="plant" tick={{ fill: "#8892a4", fontSize: 10 }} textAnchor="middle" axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#8892a4", fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} />
              <Bar dataKey="rakes" name="Rakes" radius={[4, 4, 0, 0]}>
                {stockCoverData.filter((r) => r.rakes > 0).map((_, i) => (
                  <Cell key={i} fill={COMPANY_COLORS[i % COMPANY_COLORS.length]} />
                ))}
                <LabelList dataKey="rakes" position="top" formatter={(v) => v > 0 ? v : ""} style={{ fill: "#475569", fontSize: 11, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Table */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Full Fuel Position — {reportDate}</span>
          <span className="panel-badge teal">Coal</span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Plant</th>
              <th>Opening</th>
              <th>Receipt</th>
              <th>Consumption</th>
              <th>Closing</th>
              <th>Stock Cover</th>
              <th>Generation (MU)</th>
              <th>PLF</th>
              <th>Recon</th>
            </tr>
          </thead>
          <tbody>
            {daily_fuel.map((r, i) => {
              const level = r.days_stock_cover < 5 ? "critical" : r.days_stock_cover < 10 ? "warning" : "safe";
              return (
                <tr key={i}>
                  <td>
                    <span className="fuel-plant-badge">{r.plant}</span>
                  </td>
                  <td>{mt(r.opening_balance)}</td>
                  <td>{mt(r.receipt)}</td>
                  <td>{mt(r.consumption_release)}</td>
                  <td>{mt(r.closing_balance)}</td>
                  <td>
                    <span className={`stock-cover`}>
                      <span className={`days ${level}`}>{r.days_stock_cover?.toFixed(1)}</span>
                      <span className="unit">d</span>
                    </span>
                  </td>
                  <td>{r.generation_mu?.toFixed(2) ?? "—"}</td>
                  <td>
                    <span style={{ color: r.plf_pct > 80 ? COLORS.teal : r.plf_pct > 60 ? COLORS.amber : COLORS.coral, fontWeight: 600 }}>
                      {r.plf_pct?.toFixed(1)}%
                    </span>
                  </td>
                  <td>
                    <span className={r.reconciliation_flag ? "flag-bad" : "flag-ok"} style={{ fontSize: 11 }}>
                      {r.reconciliation_flag ? `⚠ Δ${r.reconciliation_delta}` : "✓ OK"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
