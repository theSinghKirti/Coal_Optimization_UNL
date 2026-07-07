import React, { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, LabelList, Cell, ResponsiveContainer
} from "recharts";
import {
  inr, mt, shortPlant, COLORS,
  currentAllocations
} from "../lib/utils";
import LiveAllocation from "./LiveAllocation";

export default function AllocationTab({ optimization, setShowDetailsDrawer, liveData }) {
  
  const recommendedAllocations = useMemo(() => {
    const list = optimization.allocations.map(a => ({
      plant: a.plant,
      company: a.company,
      allocated_mt: a.allocated_mt,
      landed_cost_rs_mt: a.landed_cost_rs_mt
    }));
    optimization.shortfalls.forEach(s => {
      list.push({
        plant: s.plant,
        company: "Market",
        allocated_mt: s.shortfall_mt,
        landed_cost_rs_mt: s.assumed_market_rate_rs_mt
      });
    });
    return list;
  }, [optimization]);

  const baselineTotalCost = useMemo(() => {
    return currentAllocations.reduce((sum, a) => sum + a.allocated_mt * a.landed_cost_rs_mt, 0);
  }, []);

  const optimizedTotalCost = useMemo(() => {
    return recommendedAllocations.reduce((sum, a) => sum + a.allocated_mt * a.landed_cost_rs_mt, 0);
  }, [recommendedAllocations]);

  const savings = baselineTotalCost - optimizedTotalCost;
  const savingsPercent = (savings / baselineTotalCost) * 100;

  /* Bar chart data for allocation */
  const allocChartData = useMemo(() => {
    const by = {};
    optimization.allocations.forEach((a) => {
      by[a.plant] = (by[a.plant] || 0) + a.allocated_mt;
    });
    optimization.shortfalls.forEach((s) => {
      by[s.plant] = (by[s.plant] || 0); // already counted
    });
    return Object.entries(by)
      .map(([plant, allocated]) => ({
        plant: shortPlant(plant),
        allocated: Math.round(allocated),
        shortfall: Math.round(
          (optimization.shortfalls.find((s) => s.plant === plant)?.shortfall_mt) || 0
        ),
      }))
      .sort((a, b) => b.allocated - a.allocated);
  }, [optimization]);

  /* Derived allocation by plant */
  const allocByPlant = useMemo(() => {
    const m = {};
    optimization.allocations.forEach((a) => {
      m[a.plant] = m[a.plant] || [];
      m[a.plant].push(a);
    });
    optimization.shortfalls.forEach((s) => {
      m[s.plant] = m[s.plant] || [];
      m[s.plant].push({ ...s, isShortfall: true });
    });
    return m;
  }, [optimization]);

  const costCompareData = useMemo(() => {
    return [
      { 
        name: "Current Allocation Cost", 
        cost: baselineTotalCost / 1e7, 
        fill: "#475569" 
      },
      { 
        name: "Recommended Allocation Cost", 
        cost: optimizedTotalCost / 1e7, 
        fill: savings >= 0 ? "var(--teal)" : "var(--coral)" 
      },
    ];
  }, [baselineTotalCost, optimizedTotalCost, savings]);

  return (
    <div className="page-content" id="tab-allocation">

      {/* ── Phase 1B: Live Allocation Data ── */}
      {liveData && <LiveAllocation liveData={liveData} />}

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
          Cost comparison and allocation cards below use demo snapshot data, not live backend values.
        </span>
      </div>

      <p className="section-intro">
        LP-optimized coal allocation minimizing blended landed cost subject to FSA + Bridge Linkage ACQ caps.
        Market shortfall rows represent demand sourced at e-auction premium.
      </p>

      {/* Cost savings summary */}
      <div className="charts-row">
        <div className="panel" onClick={() => setShowDetailsDrawer(true)} style={{ cursor: "pointer" }}>
          <div className="panel-header">
            <span className="panel-title-graphics">Cost Comparison</span>
            <span className={`panel-badge ${savings >= 0 ? "teal" : "coral"}`}>
              {savings >= 0 ? "Savings Projected" : "Cost Increase"}
            </span>
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: savings >= 0 ? "var(--teal)" : "var(--coral)" }}>
              {savings >= 0 
                ? `Projected Savings: ₹${(savings / 1e7).toFixed(2)} Cr (${savingsPercent.toFixed(2)}%)`
                : `Projected Cost Increase: ₹${(Math.abs(savings) / 1e7).toFixed(2)} Cr (${Math.abs(savingsPercent).toFixed(2)}%)`
              }
            </div>
            {savings < 0 && (
              <div style={{ 
                marginTop: 8, 
                padding: "8px 12px", 
                background: "rgba(220,38,38,0.06)", 
                border: "1px solid rgba(220,38,38,0.15)", 
                borderRadius: "8px", 
                fontSize: "12px", 
                color: "var(--coral)",
                lineHeight: 1.4
              }}>
                <div style={{ fontWeight: 700 }}>⚠️ Optimization result needs review — projected cost increase</div>
                <div style={{ color: "var(--ink-muted)", fontSize: "11px", marginTop: 2 }}>
                  Constraint-driven allocation — lowest feasible cost under mandatory rules.
                </div>
                <div style={{ color: "var(--ink-dim)", fontSize: "10px", marginTop: 4, fontFamily: "var(--font-mono)" }}>
                  Cause: FSA ACQ caps, mandatory stock-cover limits, and source availability constraints.
                </div>
              </div>
            )}
          </div>

          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={costCompareData} layout="vertical" margin={{ left: -10, right: 60, top: 4, bottom: 4 }}>
              <CartesianGrid horizontal={false} stroke="rgba(255,255,255,0.04)" />
              <XAxis type="number" tick={{ fill: "#8892a4", fontSize: 10 }} axisLine={false} tickLine={false}
                tickFormatter={(v) => "₹" + v.toFixed(0) + " Cr"} />
              <YAxis type="category" dataKey="name" tick={{ fill: "var(--ink)", fontSize: 10, fontFamily: "var(--font-mono)" }}
                axisLine={false} tickLine={false} width={130} />
              <Bar dataKey="cost" radius={[0, 6, 6, 0]}>
                {costCompareData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                <LabelList dataKey="cost" position="right" formatter={(v) => "₹" + v.toFixed(2) + " Cr"} style={{ fill: "#475569", fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          <p style={{ marginTop: 12, fontSize: 11, color: "var(--ink-muted)", lineHeight: 1.4 }}>
            Comparison is based on the same total coal requirement for all covered plants. Optimization minimizes total landed cost while satisfying FSA ACQ, GCV, stock-cover, source availability, and linkage constraints.
          </p>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span className="panel-title-graphics">ACQ Utilisation by Plant</span>
            <span className="panel-badge amber">Capacity</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={allocChartData}
              margin={{ top: 25, right: 8, left: -12, bottom: 0 }}
            >
              <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="plant" tick={{ fill: "#8892a4", fontSize: 10 }} textAnchor="middle" axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#8892a4", fontSize: 10 }} axisLine={false} tickLine={false}
                tickFormatter={(v) => (v / 1000).toFixed(0) + "k"} />
              <Bar dataKey="allocated" name="Allocated" fill={COLORS.amber} radius={[4, 4, 0, 0]}>
                <LabelList dataKey="allocated" position="top" formatter={(v) => v > 0 ? (v/1000).toFixed(0)+"k" : ""} style={{ fill: "#475569", fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
              </Bar>
              <Bar dataKey="shortfall" name="Shortfall" fill={COLORS.coral} radius={[4, 4, 0, 0]}>
                <LabelList dataKey="shortfall" position="top" formatter={(v) => v > 0 ? (v/1000).toFixed(0)+"k" : ""} style={{ fill: COLORS.coral, fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Per-plant allocation cards */}
      {Object.entries(allocByPlant).map(([plant, rows]) => {
        const totalAlloc = rows.filter((r) => !r.isShortfall).reduce((s, r) => s + r.allocated_mt, 0);
        const nonShortfallRows = rows.filter((r) => !r.isShortfall);
        const dominantAgency = nonShortfallRows.length > 0
          ? nonShortfallRows.reduce((prev, current) => (prev.allocated_mt > current.allocated_mt) ? prev : current).company
          : "Market";
        const headerColorClass = `header-${dominantAgency.toLowerCase()}`;
        return (
          <div key={plant} className="plant-alloc-card">
            <div className={`plant-alloc-header ${headerColorClass}`}>
              <span className="plant-alloc-name">🏭 {plant}</span>
              <span className="plant-alloc-total">Dominant: {dominantAgency} | Total: {mt(totalAlloc)}</span>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Allocated</th>
                  <th>Landed Cost</th>
                  <th>ACQ Cap (Month)</th>
                  <th>Utilisation</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const agencyClass = r.isShortfall ? "row-market" : `row-${r.company.toLowerCase()}`;
                  return (
                    <tr key={i} className={agencyClass}>
                      <td>
                        {r.isShortfall
                          ? <span className="tag tag-market">⚡ Market</span>
                          : <span className={`tag tag-${r.company.toLowerCase()}`}>{r.company}</span>}
                      </td>
                      <td>{mt(r.isShortfall ? r.shortfall_mt : r.allocated_mt)}</td>
                      <td>{inr(r.isShortfall ? r.assumed_market_rate_rs_mt : r.landed_cost_rs_mt)}/MT</td>
                      <td>{r.isShortfall ? "—" : mt(r.acq_cap_mt)}</td>
                      <td>
                        {r.isShortfall ? (
                          <span className="flag-bad" style={{ fontSize: 11 }}>over cap</span>
                        ) : (
                          <div className="util-wrap">
                            <div className="util-track">
                              <div
                                className={`util-fill${r.acq_utilisation_pct > 100 ? " over" : ""}`}
                                style={{ width: Math.min(100, r.acq_utilisation_pct) + "%" }}
                              />
                            </div>
                            <span className="util-pct">{r.acq_utilisation_pct?.toFixed(1)}%</span>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
