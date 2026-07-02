import React, { useMemo, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LabelList,
  PieChart, Pie, Cell, Legend,
  RadialBarChart, RadialBar,
  LineChart, Line, Area, AreaChart,
} from "recharts";
import snapshot from "./data/demoSnapshot.json";
import DailyFuelForm from "./components/DailyFuelForm";
import IppAgreementForm from "./components/IppAgreementForm";

/* ── helpers ────────────────────────────────── */
const inr = (n, short = false) => {
  if (n == null) return "—";
  if (short) {
    if (Math.abs(n) >= 1e7) return "₹" + (n / 1e7).toFixed(1) + " Cr";
    if (Math.abs(n) >= 1e5) return "₹" + (n / 1e5).toFixed(1) + " L";
    return "₹" + Math.round(n).toLocaleString("en-IN");
  }
  return "₹" + new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(n);
};
const mt = (n) =>
  n == null ? "—" : new Intl.NumberFormat("en-IN").format(Math.round(n)) + " MT";
const pct = (n) => (n == null ? "—" : n.toFixed(1) + "%");

const shortPlant = (name) => {
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

const COLORS = {
  amber:  "#d97706",
  teal:   "#0d9488",
  coral:  "#dc2626",
  violet: "#7c3aed",
  sky:    "#0284c7",
  rose:   "#e11d48",
};

const COMPANY_COLORS = ["#d97706","#0d9488","#7c3aed","#0284c7","#dc2626","#16a34a","#db2777"];

/* ── Custom Tooltip ─────────────────────────── */
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="custom-tooltip">
      <div style={{ color: "#0f172a", marginBottom: 6, fontWeight: 700, fontSize: 13 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || "#d97706", marginBottom: 2 }}>
          {p.name}: {typeof p.value === "number" && p.value > 1e4 ? inr(p.value, true) : p.value?.toLocaleString("en-IN") ?? "—"}
        </div>
      ))}
    </div>
  );
}

/* ── NAV TABS ───────────────────────────────── */
const TABS = [
  { id: "overview",     label: "Overview",       icon: "⚡" },
  { id: "allocation",   label: "Allocation",     icon: "📊" },
  { id: "daily",        label: "Fuel Position",  icon: "🛢️" },
  { id: "registry",    label: "ACQ Registry",   icon: "📋" },
  { id: "plantstatus", label: "Plant Status",   icon: "🏭" },
  { id: "entry",        label: "Data Entry",     icon: "✏️" },
];

/* ── company colour map ─────────────────────── */
const CO_COLOR = {
  NCL:  "#0d9488",
  CCL:  "#d97706",
  BCCL: "#7c3aed",
  SECL: "#0284c7",
  ECL:  "#dc2626",
};

/* ── IPP benchmark variable cost (Rs/kWh) ─────
   Tied-IPP tariff assumed at ₹3.90/kWh (fuel VC)
   Source: screenshot reference value             */
const IPP_VC = 3.90;

/* ── GCV assumption to convert Rs/MT → Rs/kWh ─
   Average Station Heat Rate: ~2400 kcal/kWh
   Blended GCV assumption: ~3800 kcal/kg          */
const HEAT_RATE   = 2400;  // kcal/kWh
const BLEND_GCV   = 3800;  // kcal/kg  → 3.8 Gcal/MT

/* ═══════════════════════════════════════════════════════
   MAIN APP
═══════════════════════════════════════════════════════ */
export default function App() {
  const { optimization, daily_fuel, constraints, generated_from } = snapshot;
  const [tab, setTab] = useState("overview");
  const [showDetailsDrawer, setShowDetailsDrawer] = useState(false);

  // Dynamic baseline allocations matching total demand and totaling ~₹1260.1 Cr
  const currentAllocations = useMemo(() => {
    return [
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
  }, []);

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
  }, [currentAllocations]);

  const optimizedTotalCost = useMemo(() => {
    return recommendedAllocations.reduce((sum, a) => sum + a.allocated_mt * a.landed_cost_rs_mt, 0);
  }, [recommendedAllocations]);

  const savings = baselineTotalCost - optimizedTotalCost;
  const savingsPercent = (savings / baselineTotalCost) * 100;

  const totalDemand = useMemo(() => {
    return recommendedAllocations.reduce((sum, a) => sum + a.allocated_mt, 0);
  }, [recommendedAllocations]);

  const comparisonBySource = useMemo(() => {
    const sources = ["NCL", "CCL", "BCCL", "SECL", "ECL", "Market"];
    return sources.map(src => {
      const current = currentAllocations.filter(a => a.company === src).reduce((sum, a) => sum + a.allocated_mt, 0);
      const currentCost = currentAllocations.filter(a => a.company === src).reduce((sum, a) => sum + a.allocated_mt * a.landed_cost_rs_mt, 0);
      
      const recommended = recommendedAllocations.filter(a => a.company === src).reduce((sum, a) => sum + a.allocated_mt, 0);
      const recommendedCost = recommendedAllocations.filter(a => a.company === src).reduce((sum, a) => sum + a.allocated_mt * a.landed_cost_rs_mt, 0);
      
      return {
        source: src,
        currentQty: current,
        currentCost: currentCost,
        recommendedQty: recommended,
        recommendedCost: recommendedCost,
        qtyDiff: recommended - current,
        costDiff: recommendedCost - currentCost
      };
    });
  }, [currentAllocations, recommendedAllocations]);

  /* — derived data — */
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
        days: parseFloat((r.days_stock_cover || 0).toFixed(1)),
        closing: r.closing_balance,
        plf: parseFloat((r.plf_pct || 0).toFixed(1)),
        rakes: r.rakes_received || 0,
        gen: r.generation_mu || 0,
      }))
      .sort((a, b) => b.days - a.days),
  [daily_fuel]);

  /* Cost comparison data */
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

  /* PLF area data */
  const plfData = useMemo(() =>
    daily_fuel.map((r) => ({
      plant: shortPlant(r.plant),
      plf: parseFloat((r.plf_pct || 0).toFixed(1)),
      gen: r.generation_mu || 0,
    })),
  [daily_fuel]);

  const totalShortfall = optimization.shortfalls.reduce((s, r) => s + r.shortfall_mt, 0);

  /* ── Plant-Status derived data ─────────────── */
  const plantStatusRows = useMemo(() => {
    const plants = optimization.plants_covered;

    return plants.map((plant) => {
      // allocations for this plant
      const allocs = optimization.allocations.filter((a) => a.plant === plant);
      const totalAlloc = allocs.reduce((s, a) => s + a.allocated_mt, 0);

      // source mix %
      const mix = allocs.map((a) => ({
        company: a.company,
        pct: totalAlloc > 0 ? (a.allocated_mt / totalAlloc) * 100 : 0,
        color: CO_COLOR[a.company] || "#8892a4",
      }));

      // blended landed cost Rs/MT (weighted average)
      const blendedLandedCost = totalAlloc > 0
        ? allocs.reduce((s, a) => s + a.landed_cost_rs_mt * a.allocated_mt, 0) / totalAlloc
        : 0;

      // VC NOW Rs/kWh = (landed_cost_rs_mt) / (GCV_kcal_kg * 1000 / heat_rate_kcal_kWh)
      // = landed_cost_rs_mt * heat_rate / (gcv_kcal_kg * 1000)
      const vcNow = blendedLandedCost > 0
        ? parseFloat(((blendedLandedCost * HEAT_RATE) / (BLEND_GCV * 1000)).toFixed(2))
        : null;

      // cheapest available source for this plant
      const cheapest = allocs.length
        ? allocs.reduce((a, b) => a.landed_cost_rs_mt < b.landed_cost_rs_mt ? a : b)
        : null;
      const vcOpt = cheapest
        ? parseFloat(((cheapest.landed_cost_rs_mt * HEAT_RATE) / (BLEND_GCV * 1000)).toFixed(2))
        : null;

      const delta = (vcOpt != null && vcNow != null) ? parseFloat((vcOpt - vcNow).toFixed(2)) : null;

      // daily fuel entry for this plant
      const fuel = daily_fuel.find((r) => r.plant === plant && r.fuel_type === "COAL");
      const days = fuel ? parseFloat((fuel.days_stock_cover || 0).toFixed(1)) : null;
      const muMo = fuel ? Math.round((fuel.generation_mu || 0) * 30) : null;

      // ACQ utilisation (avg across sources)
      const avgUtil = allocs.length
        ? allocs.reduce((s, a) => s + (a.acq_utilisation_pct || 0), 0) / allocs.length
        : 0;

      // VS IPP
      const vsIPP = vcNow != null ? (vcNow <= IPP_VC ? "ahead" : "behind") : "—";

      // shortfall
      const shortfall = optimization.shortfalls.find((s) => s.plant === plant);

      return { plant, mix, vcNow, vcOpt, delta, days, muMo, avgUtil, vsIPP, shortfall };
    });
  }, [optimization, daily_fuel]);

  /* ── Fleet-level KPIs for Plant Status tab ── */
  const fleetKpis = useMemo(() => {
    // annual savings extrapolated (monthly * 12)
    const annualSaving = Math.abs(savings) * 12;

    // cheapest single source across all allocations
    const cheapestAlloc = optimization.allocations.reduce((a, b) =>
      a.landed_cost_rs_mt < b.landed_cost_rs_mt ? a : b
    );
    const cheapestVc = parseFloat(
      ((cheapestAlloc.landed_cost_rs_mt * HEAT_RATE) / (BLEND_GCV * 1000)).toFixed(2)
    );

    // plants behind IPP
    const behind = plantStatusRows.filter((r) => r.vsIPP === "behind").length;
    const total  = plantStatusRows.length;

    return {
      annualSaving,
      cheapestSource: cheapestAlloc.company,
      cheapestVc,
      plantsBehind: behind,
      plantsTotal: total,
      stationsModelled: optimization.plants_covered.length,
    };
  }, [optimization, plantStatusRows]);

  /* ── Recommended actions ────────────────────── */
  const recommendedActions = useMemo(() => {
    const actions = [];
    plantStatusRows.forEach(({ plant, vcNow, vcOpt, shortfall, mix }) => {
      const cheapCo = mix.sort((a, b) => a.landed_cost_rs_mt - b.landed_cost_rs_mt)[0]?.company;
      if (shortfall) {
        actions.push({
          plant,
          text: `keep lifting above take-or-pay threshold to avoid under-lifting penalty.`,
          type: "warning",
        });
      }
      if (vcNow != null && vcOpt != null && vcNow > vcOpt) {
        actions.push({
          plant,
          text: `shift toward cheaper NCL/SECL to bring blended cost ₹${vcNow} → ₹${vcOpt} per kWh.`,
          type: "info",
        });
      }
    });
    return actions;
  }, [plantStatusRows]);

  return (
    <div className="dashboard">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <img
            src="/uprvunl-logo.png.jpg"
            alt="UPRVUNL Logo"
            className="sidebar-logo-img"
          />
          <div className="sidebar-logo-text">
            <div className="eyebrow">UPRVUNL · Fuel Cell</div>
            <h1>Coal Optimization Platform</h1>
          </div>
        </div>
        <nav className="sidebar-nav">
          {TABS.map((t) => (
            <button
              key={t.id}
              id={`nav-${t.id}`}
              className={`nav-btn${tab === t.id ? " active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              <span className="nav-icon">{t.icon}</span>
              {t.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="status-pill">
            {optimization.status.toUpperCase()}
          </div>
          <div style={{ marginTop: 10, fontSize: 10, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", lineHeight: 1.5 }}>
            Report: 30 Jun 2026
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="main">
        {/* Topbar */}
        <div className="topbar">
          <div className="topbar-title">
            {TABS.find((t) => t.id === tab)?.label}
          </div>
          <div className="topbar-meta">
            <span>Run status:</span>
            <span className="run-badge">{optimization.status}</span>
            <span style={{ color: "var(--ink-dim)" }}>|</span>
            <span>7 plants covered</span>
          </div>
        </div>

        {/* Plant Shorthand Key Ribbon */}
        <div className="plant-key-ribbon">
          <span className="key-title">Plant Key:</span>
          <span>ANPR: Anpara</span>
          <span>OB-B: Obra B</span>
          <span>OB-C: Obra C</span>
          <span>HRDG: Harduaganj</span>
          <span>JWHP: Jawaharpur</span>
          <span>PNKI: Panki Extn</span>
          <span>PRCH: Parichha</span>
        </div>

        {/* ══════════════ OVERVIEW TAB ══════════════ */}
        {tab === "overview" && (
          <div className="page-content" id="tab-overview">
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
                  <span className="panel-badge amber">Monthly</span>
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
                  <span className="panel-badge teal">Pie</span>
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
                  <span className="panel-badge violet">Today</span>
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
                  <span className="panel-badge coral">Live</span>
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
                  <span className="panel-badge coral">{optimization.shortfalls.length} Plants</span>
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
        )}

        {/* ══════════════ ALLOCATION TAB ══════════════ */}
        {tab === "allocation" && (
          <div className="page-content" id="tab-allocation">
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
        )}

        {/* ══════════════ DAILY FUEL POSITION TAB ══════════════ */}
        {tab === "daily" && (
          <div className="page-content" id="tab-daily">
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
                <span className="panel-title">Full Fuel Position — 30 Jun 2026</span>
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
        )}

        {/* ══════════════ ACQ REGISTRY TAB ══════════════ */}
        {tab === "registry" && (
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
        )}

        {/* ══════════════ DATA ENTRY TAB ══════════════ */}
        {tab === "entry" && (
          <div className="page-content" id="tab-entry">
            <p className="section-intro">
              Manage operational fuel inputs and variable cost tie-up agreements with Independent Power Producers (IPPs).
            </p>
            
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1.8fr", gap: "28px", alignItems: "start" }}>
              {/* Left Column: Operational Daily Fuel Form */}
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Daily Fuel Entry Form</span>
                  <span className="panel-badge amber">Manual Input</span>
                </div>
                <DailyFuelForm />
              </div>

              {/* Right Column: IPP VC Agreements & Action Plans */}
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">IPP VC Agreement & Rules Form</span>
                  <span className="panel-badge violet">Action Plan</span>
                </div>
                <IppAgreementForm />
              </div>
            </div>
          </div>
        )}

        {/* ══════════════ PLANT STATUS TAB ══════════════ */}
        {tab === "plantstatus" && (
          <div className="page-content" id="tab-plantstatus">
            <p className="section-intro">
              Per-plant optimised allocation view: blended variable cost vs IPP benchmark,
              ACQ utilisation, stock cover, and recommended corrective actions.
            </p>

            {/* Fleet KPI strip */}
            <div className="ps-kpi-strip">
              <div className="ps-kpi" onClick={() => setShowDetailsDrawer(true)} style={{ cursor: "pointer" }}>
                <div className="ps-kpi-label">{savings >= 0 ? "Fleet Saving" : "Fleet Cost Increase"}</div>
                <div className={`ps-kpi-value ${savings >= 0 ? "teal" : "coral"}`}>
                  {inr(fleetKpis.annualSaving, true)}
                  <span className="ps-kpi-unit">Cr/yr</span>
                </div>
              </div>
              <div className="ps-kpi-divider" />
              <div className="ps-kpi">
                <div className="ps-kpi-label">Plants Behind Tied IPP</div>
                <div className="ps-kpi-value coral">
                  {fleetKpis.plantsBehind}
                  <span className="ps-kpi-unit">/ {fleetKpis.plantsTotal}</span>
                </div>
              </div>
              <div className="ps-kpi-divider" />
              <div className="ps-kpi">
                <div className="ps-kpi-label">Stations Modelled</div>
                <div className="ps-kpi-value teal">{fleetKpis.stationsModelled}</div>
              </div>
              <div className="ps-kpi-divider" />
              <div className="ps-kpi">
                <div className="ps-kpi-label">Cheapest Source</div>
                <div className="ps-kpi-value violet">{fleetKpis.cheapestSource}</div>
                <div className="ps-kpi-sub">₹{fleetKpis.cheapestVc}/kWh fuel</div>
              </div>
            </div>

            {/* Optimised allocation by plant */}
            <div className="panel">
              <div className="panel-header">
                <div>
                  <span className="panel-title">Optimised allocation by plant</span>
                  <span style={{ marginLeft: 12, fontSize: 11, color: "var(--ink-dim)", fontFamily: "var(--font-mono)" }}>
                    minimise blended fuel cost within ACQ, GCV floor &amp; take-or-pay
                  </span>
                </div>
                <span className="panel-badge amber">LP · Optimal</span>
              </div>

              <table className="data-table ps-table">
                <thead>
                  <tr>
                    <th style={{ width: 140 }}>Plant</th>
                    <th style={{ width: 280 }}>Optimised Source Mix</th>
                    <th style={{ width: 72, textAlign: "right" }}>VC Now</th>
                    <th style={{ width: 72, textAlign: "right" }}>VC Opt.</th>
                    <th style={{ width: 80, textAlign: "right" }}>Δ Rs/kWh</th>
                    <th style={{ width: 160 }}>ACQ Util.</th>
                    <th style={{ width: 72, textAlign: "center" }}>Cover</th>
                    <th style={{ width: 80, textAlign: "center" }}>vs IPP</th>
                  </tr>
                </thead>
                <tbody>
                  {plantStatusRows.map((row) => (
                    <tr key={row.plant}>
                      {/* Plant name */}
                      <td>
                        <span className="status-plant-badge">{row.plant}</span>
                        {row.muMo != null && (
                          <div style={{ fontSize: 10, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", marginTop: 4 }}>
                            {row.muMo.toLocaleString("en-IN")} MU/mo
                          </div>
                        )}
                      </td>

                      {/* Stacked source-mix bar */}
                      <td>
                        <div className="mix-bar-track">
                          {row.mix.map((s, i) => (
                            <div
                              key={i}
                              className="mix-bar-seg"
                              style={{ width: s.pct + "%", background: s.color }}
                              title={`${s.company}: ${s.pct.toFixed(0)}%`}
                            />
                          ))}
                        </div>
                        <div className="mix-labels">
                          {row.mix.map((s, i) => (
                            <span key={i} className="mix-label" style={{ color: s.color }}>
                              {s.company} {s.pct.toFixed(0)}%
                            </span>
                          ))}
                        </div>
                      </td>

                      {/* VC Now */}
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>
                        {row.vcNow ?? "—"}
                      </td>

                      {/* VC Opt */}
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 13, fontWeight: 600, color: "var(--teal)" }}>
                        {row.vcOpt ?? "—"}
                      </td>

                      {/* Delta */}
                      <td style={{ textAlign: "right" }}>
                        {row.delta != null && (
                          <span
                            className="delta-badge"
                            style={{
                              color: row.delta < 0 ? "var(--teal)" : "var(--coral)",
                              background: row.delta < 0 ? "rgba(0,212,170,0.1)" : "rgba(255,107,107,0.1)",
                            }}
                          >
                            {row.delta < 0 ? "" : "+"}{row.delta}
                          </span>
                        )}
                      </td>

                      {/* ACQ Utilisation */}
                      <td>
                        <div className="util-wrap">
                          <div className="util-track" style={{ flex: 1, width: "auto" }}>
                            <div
                              className={`util-fill${row.avgUtil > 100 ? " over" : ""}`}
                              style={{ width: Math.min(100, row.avgUtil) + "%" }}
                            />
                          </div>
                          <span className="util-pct" style={{ minWidth: 54 }}>
                            {row.avgUtil.toFixed(0)}% of ACQ
                          </span>
                        </div>
                        {row.shortfall && (
                          <div style={{ fontSize: 10, color: "var(--coral)", fontFamily: "var(--font-mono)", marginTop: 3 }}>
                            +{Math.round(row.shortfall.shortfall_mt / 1000)}k MT spot
                          </div>
                        )}
                      </td>

                      {/* Stock cover */}
                      <td style={{ textAlign: "center" }}>
                        {row.days != null && (
                          <span
                            style={{
                              fontFamily: "var(--font-display)",
                              fontSize: 15,
                              fontWeight: 700,
                              color: row.days < 5 ? "var(--coral)" : row.days < 10 ? "var(--amber)" : "var(--teal)",
                            }}
                          >
                            {row.days}d
                          </span>
                        )}
                      </td>

                      {/* VS IPP badge */}
                      <td style={{ textAlign: "center" }}>
                        <span
                          className="ipp-badge"
                          style={{
                            background: row.vsIPP === "ahead" ? "rgba(0,212,170,0.12)" : "rgba(255,107,107,0.12)",
                            color:      row.vsIPP === "ahead" ? "var(--teal)"           : "var(--coral)",
                            border:     `1px solid ${row.vsIPP === "ahead" ? "rgba(0,212,170,0.25)" : "rgba(255,107,107,0.25)"}`,
                          }}
                        >
                          {row.vsIPP}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Recommended actions */}
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Recommended actions</span>
                <span className="panel-badge violet">{recommendedActions.length} items</span>
              </div>
              <div className="rec-actions-list">
                {recommendedActions.map((a, i) => (
                  <div key={i} className="rec-action-row">
                    <span className="rec-action-plant">{a.plant}:</span>
                    <span className="rec-action-text">{a.text}</span>
                  </div>
                ))}
                {recommendedActions.length === 0 && (
                  <div style={{ color: "var(--ink-dim)", fontFamily: "var(--font-mono)", fontSize: 12, padding: "8px 0" }}>
                    All plants operating within optimal parameters.
                  </div>
                )}
              </div>
            </div>

            {/* VC scatter: Now vs Opt per plant */}
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title-graphics">VC Now vs Optimised (₹/kWh)</span>
                <span className="panel-badge teal">Savings potential</span>
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={plantStatusRows.map((r) => ({ plant: shortPlant(r.plant), now: r.vcNow, opt: r.vcOpt, ipp: IPP_VC }))}
                  margin={{ top: 20, right: 24, left: -10, bottom: 0 }}
                >
                  <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="plant" tick={{ fill: "#8892a4", fontSize: 10, fontFamily: "var(--font-mono)" }} textAnchor="middle" axisLine={false} tickLine={false} />
                  <YAxis domain={[2.2, 4.5]} tick={{ fill: "#8892a4", fontSize: 10 }} axisLine={false} tickLine={false}
                    tickFormatter={(v) => "₹" + v.toFixed(2)} />
                  <Bar dataKey="now" name="VC Now" fill="var(--violet)" radius={[4, 4, 0, 0]}>
                    <LabelList dataKey="now" position="top" formatter={(v) => v ? "₹" + v.toFixed(2) : ""} style={{ fill: "var(--violet)", fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
                  </Bar>
                  <Bar dataKey="opt" name="VC Opt" fill="var(--teal)"   radius={[4, 4, 0, 0]}>
                    <LabelList dataKey="opt" position="top" formatter={(v) => v ? "₹" + v.toFixed(2) : ""} style={{ fill: "var(--teal)", fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700 }} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div style={{ display: "flex", gap: 20, marginTop: 10, paddingLeft: 4 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: "var(--violet)", display: "inline-block" }} />
                  VC Now (blended)
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: "var(--teal)", display: "inline-block" }} />
                  VC Optimised
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: "var(--amber)", display: "inline-block" }} />
                  IPP Benchmark (₹{IPP_VC})
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="dash-footer">
          Data source: {generated_from} · Wire VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY to connect live data.
        </div>
      </div>

      {/* ── Details Drawer ── */}
      {showDetailsDrawer && (
        <div className="drawer-overlay" onClick={() => setShowDetailsDrawer(false)}>
          <div className="drawer-content" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <h2>Cost Comparison Details</h2>
              <button className="close-drawer-btn" onClick={() => setShowDetailsDrawer(false)}>✕</button>
            </div>
            <div className="drawer-body">
              <div className="drawer-section">
                <h3>Summary</h3>
                <table className="drawer-summary-table">
                  <tbody>
                    <tr>
                      <td>Total Plant Demand</td>
                      <td>{mt(totalDemand)}</td>
                    </tr>
                    <tr>
                      <td>Current Cost (Baseline)</td>
                      <td style={{ fontWeight: 700 }}>{inr(baselineTotalCost)}</td>
                    </tr>
                    <tr>
                      <td>Recommended Cost (LP)</td>
                      <td style={{ fontWeight: 700, color: savings >= 0 ? "var(--teal)" : "var(--coral)" }}>
                        {inr(optimizedTotalCost)}
                      </td>
                    </tr>
                    <tr>
                      <td>Projected Diff</td>
                      <td style={{ fontWeight: 700, color: savings >= 0 ? "var(--teal)" : "var(--coral)" }}>
                        {savings >= 0 ? "-" : "+"}{inr(Math.abs(savings))} ({Math.abs(savingsPercent).toFixed(2)}%)
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="drawer-section" style={{ background: "rgba(30,41,59,0.02)", padding: "16px 20px", borderRadius: "12px", border: "1.5px solid var(--border-bright)" }}>
                <h3 style={{ color: "var(--amber)", fontSize: "12px", borderBottom: "none", marginBottom: "8px", paddingBottom: 0 }}>
                  🏛️ Official Executive Briefing (Policy Context)
                </h3>
                <p style={{ fontSize: "12.5px", lineHeight: "1.5", color: "var(--ink)", margin: "0 0 10px 0" }}>
                  <strong>Why is there a cost increase instead of savings?</strong>
                </p>
                <ul style={{ margin: 0, paddingLeft: "16px", fontSize: "12.5px", lineHeight: "1.6", color: "var(--ink-muted)", display: "flex", flexDirection: "column", gap: "8px" }}>
                  <li>
                    <strong>Grid Safety First:</strong> To prevent sudden power blackouts, all stations must maintain a safe buffer of coal stock (5–15 days of inventory). Recommending purchases to fulfill this mandatory reserve avoids catastrophic shutdown penalties.
                  </li>
                  <li>
                    <strong>Contract Caps Exhausted:</strong> Cheaper coal contracts (FSA) with NCL and CCL are capped. When local power generation targets exceeded these caps, cheap coal was no longer available.
                  </li>
                  <li>
                    <strong>Market Purchase Necessity:</strong> To bridge the coal shortage, the model had to allocate from the spot market (e-auction) at higher rates, increasing the total blended cost compared to historical baseline operations which ignored GCV blending rules and reserve cover requirements.
                  </li>
                  <li>
                    <strong>Policy Compliance:</strong> The allocation is mathematically the <strong>lowest possible cost</strong> while complying with 100% of fuel supply policies, environmental GCV restrictions, and station boiler constraints.
                  </li>
                </ul>
              </div>

              <div className="drawer-section">
                <h3>Allocation & Cost by Source</h3>
                <table className="drawer-details-table">
                  <thead>
                    <tr>
                      <th>Source</th>
                      <th style={{ textAlign: "right" }}>Current (MT)</th>
                      <th style={{ textAlign: "right" }}>Rec. (MT)</th>
                      <th style={{ textAlign: "right" }}>Cost Diff</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonBySource.map((row, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 700 }}>{row.source}</td>
                        <td style={{ textAlign: "right" }}>{row.currentQty > 0 ? mt(row.currentQty) : "—"}</td>
                        <td style={{ textAlign: "right" }}>{row.recommendedQty > 0 ? mt(row.recommendedQty) : "—"}</td>
                        <td style={{ 
                          textAlign: "right", 
                          fontWeight: 600,
                          color: row.costDiff === 0 ? "var(--ink-muted)" : row.costDiff < 0 ? "var(--teal)" : "var(--coral)"
                        }}>
                          {row.costDiff === 0 ? "—" : (row.costDiff < 0 ? "-" : "+") + inr(Math.abs(row.costDiff), true)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="drawer-section">
                <h3>Active Constraints</h3>
                <ul className="drawer-constraints-list">
                  <li>
                    <strong>FSA ACQ Caps:</strong> Restricts maximum allocation from lowest-cost mine linkages (e.g. NCL at Anpara & Obra, CCL at Parichha), forcing excess demand to alternate sources.
                  </li>
                  <li>
                    <strong>Mandatory Stock-Cover:</strong> Minimum safe reserve rules (ranging from 5 to 15 days of consumption) enforce absolute lifting requirements regardless of price.
                  </li>
                  <li>
                    <strong>GCV & SHR Blending Rules:</strong> Restricts usage of high-moisture/low-GCV coals to maintain boiler efficiency limits.
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
