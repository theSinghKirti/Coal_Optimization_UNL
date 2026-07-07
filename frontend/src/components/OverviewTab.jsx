import React, { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, LabelList,
  PieChart, Pie, Cell, Legend, ResponsiveContainer
} from "recharts";
import {
  inr, mt, pct, shortPlant, COLORS, COMPANY_COLORS, CustomTooltip,
  currentAllocations
} from "../lib/utils";
import LiveBackendStatus from "./LiveBackendStatus";

export default function OverviewTab({ optimization, daily_fuel, constraints, setShowDetailsDrawer, liveData }) {
  
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
  const totalShortfall = optimization.shortfalls.reduce((s, r) => s + r.shortfall_mt, 0);

  /* Bar chart: allocated MT per plant */
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

  /* Pie chart: allocation by company */
  const companyPie = useMemo(() => {
    const by = {};
    optimization.allocations.forEach((a) => {
      by[a.company] = (by[a.company] || 0) + a.allocated_mt;
    });
    return Object.entries(by).map(([name, value]) => ({ name, value: Math.round(value) }));
  }, [optimization]);

  /* Radial chart: stock cover per plant */
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

  /* PLF area data */
  const plfData = useMemo(() =>
    daily_fuel.map((r) => ({
      plant: shortPlant(r.plant),
      plf: parseFloat(Number(r.plf_pct || 0).toFixed(1)),
      gen: r.generation_mu || 0,
    })),
  [daily_fuel]);


  return (
    <div className="page-content" id="tab-overview">
      {/* ── Phase 1A: Live Backend Status panel ── */}
      {liveData && <LiveBackendStatus liveData={liveData} />}

      {/* Demo Dashboard Metrics Section */}
      <div style={{ marginTop: 24, marginBottom: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: "var(--ink-muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
          Comparison Metrics & Alerts
        </h3>
        <span className="panel-badge violet" style={{ background: "rgba(124,58,237,0.1)", border: "1.5px solid rgba(124,58,237,0.3)" }}>DEMO DATA</span>
      </div>

      {/* KPI Row */}
      <div className="kpi-grid">
        <div className="kpi-card amber" onClick={() => setShowDetailsDrawer(true)} style={{ cursor: "pointer" }}>
          <span className="kpi-icon">💰</span>
          <div className="kpi-label">Optimized Cost</div>
          <div className="kpi-value">{inr(optimizedTotalCost, true)}</div>
          <div className="kpi-sub">Recommended allocation</div>
        </div>
        <div className="kpi-card violet" onClick={() => setShowDetailsDrawer(true)} style={{ cursor: "pointer" }}>
          <span className="kpi-icon">📈</span>
          <div className="kpi-label">Baseline Cost</div>
          <div className="kpi-value">{inr(baselineTotalCost, true)}</div>
          <div className="kpi-sub">Current allocation</div>
        </div>
        <div className={`kpi-card ${savings >= 0 ? "teal" : "coral"}`} onClick={() => setShowDetailsDrawer(true)} style={{ cursor: "pointer" }}>
          <span className="kpi-icon">{savings >= 0 ? "✨" : "⚠️"}</span>
          <div className="kpi-label">{savings >= 0 ? "Est. Savings" : "Est. Increase"}</div>
          <div className="kpi-value">{inr(Math.abs(savings), true)}</div>
          <div className="kpi-sub">{Math.abs(savingsPercent).toFixed(2)}% vs baseline</div>
        </div>
        <div className="kpi-card coral" onClick={() => setShowDetailsDrawer(true)} style={{ cursor: "pointer" }}>
          <span className="kpi-icon">⚠️</span>
          <div className="kpi-label">Market Shortfall</div>
          <div className="kpi-value">{mt(totalShortfall)}</div>
          <div className="kpi-sub">{optimization.shortfalls.length} plant(s) above cap</div>
        </div>
      </div>

      {/* Charts Row 1 */}
      <div className="charts-row">
        {/* Allocation by plant */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title-graphics">Allocation by Plant (MT)</span>
            <span className="panel-badge violet" style={{ background: "rgba(124,58,237,0.1)", border: "1.5px solid rgba(124,58,237,0.3)" }}>DEMO DATA</span>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={allocChartData} margin={{ top: 25, right: 8, left: -8, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
              <XAxis
                dataKey="plant"
                tick={{ fill: "#8892a4", fontSize: 10, fontFamily: "var(--font-mono)" }}
                textAnchor="middle"
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#8892a4", fontSize: 10, fontFamily: "var(--font-mono)" }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => (v / 1000).toFixed(0) + "k"}
              />
              <Bar dataKey="allocated" name="Allocated MT" fill={COLORS.amber} radius={[4, 4, 0, 0]}>
                <LabelList dataKey="allocated" position="top" formatter={(v) => v > 0 ? (v/1000).toFixed(0)+"k" : ""} style={{ fill: "#475569", fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
              </Bar>
              <Bar dataKey="shortfall" name="Shortfall MT" fill={COLORS.coral} radius={[4, 4, 0, 0]}>
                <LabelList dataKey="shortfall" position="top" formatter={(v) => v > 0 ? (v/1000).toFixed(0)+"k" : ""} style={{ fill: COLORS.coral, fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Company Pie */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title-graphics">Allocation by Company</span>
            <span className="panel-badge violet" style={{ background: "rgba(124,58,237,0.1)", border: "1.5px solid rgba(124,58,237,0.3)" }}>DEMO DATA</span>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={companyPie}
                cx="50%"
                cy="46%"
                innerRadius={55}
                outerRadius={85}
                paddingAngle={3}
                dataKey="value"
                nameKey="name"
                label={({ payload, percent }) =>
                  `${payload.name} ${(percent*100).toFixed(0)}%`
                }
                labelLine={{ stroke: "#94a3b8", strokeWidth: 1 }}
              >
                {companyPie.map((_, i) => (
                  <Cell key={i} fill={COMPANY_COLORS[i % COMPANY_COLORS.length]} stroke="transparent" />
                ))}
              </Pie>
              <Legend
                formatter={(value) => (
                  <span style={{ color: "#8892a4", fontSize: 11, fontFamily: "var(--font-mono)" }}>{value}</span>
                )}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="charts-row">
        {/* PLF Bar */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title-graphics">Plant Load Factor (%)</span>
            <span className="panel-badge violet" style={{ background: "rgba(124,58,237,0.1)", border: "1.5px solid rgba(124,58,237,0.3)" }}>DEMO DATA</span>
          </div>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={plfData} margin={{ top: 25, right: 8, left: -12, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
              <XAxis
                dataKey="plant"
                tick={{ fill: "#8892a4", fontSize: 10, fontFamily: "var(--font-mono)" }}
                textAnchor="middle"
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: "#8892a4", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => v + "%"}
              />
              <Bar dataKey="plf" name="PLF %" fill={COLORS.violet} radius={[4, 4, 0, 0]}>
                <LabelList dataKey="plf" position="top" formatter={(v) => v > 0 ? v.toFixed(1)+"%" : ""} style={{ fill: COLORS.violet, fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
              </Bar>
              <Bar dataKey="gen" name="Gen MU" fill={COLORS.sky} radius={[4, 4, 0, 0]}>
                <LabelList dataKey="gen" position="top" formatter={(v) => v > 0 ? v.toFixed(1) : ""} style={{ fill: COLORS.sky, fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Stock cover days */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title-graphics">Stock Cover (Days)</span>
            <span className="panel-badge violet" style={{ background: "rgba(124,58,237,0.1)", border: "1.5px solid rgba(124,58,237,0.3)" }}>DEMO DATA</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 4 }}>
            {stockCoverData.map((r) => {
              const level = r.days < 5 ? "critical" : r.days < 10 ? "warning" : "safe";
              const fillColor = level === "critical" ? COLORS.coral : level === "warning" ? COLORS.amber : COLORS.teal;
              const pctFill = Math.min(100, (r.days / 20) * 100);
              return (
                <div key={r.fullPlant} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ width: 80, fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-muted)", flexShrink: 0 }}>
                    {r.plant.replace("\n", " ").split(" ")[0]}
                  </div>
                  <div style={{ flex: 1, height: 8, background: "rgba(255,255,255,0.05)", borderRadius: 6, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: pctFill + "%", background: fillColor, borderRadius: 6, transition: "width 0.8s ease" }} />
                  </div>
                  <div style={{ width: 36, textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 12, color: fillColor, fontWeight: 700 }}>
                    {r.days}d
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Shortfalls */}
      {optimization.shortfalls.length > 0 && (
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">⚠️ Market Shortfall Alerts</span>
            <span className="panel-badge violet" style={{ background: "rgba(124,58,237,0.1)", border: "1.5px solid rgba(124,58,237,0.3)" }}>DEMO DATA</span>
          </div>
          <div className="shortfall-list">
            {optimization.shortfalls.map((s, i) => (
              <div className="shortfall-item" key={i}>
                <div>
                  <div className="shortfall-plant">{s.plant}</div>
                  <div className="shortfall-rate">Spot market @ {inr(s.assumed_market_rate_rs_mt)}/MT</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div className="shortfall-qty">{mt(s.shortfall_mt)}</div>
                  <div style={{ fontSize: 10, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", marginTop: 2 }}>
                    above FSA + Bridge cap
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
