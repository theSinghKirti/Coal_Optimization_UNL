import React, { useMemo, useState, useEffect } from "react";
import snapshot from "./data/demoSnapshot.json";

// Import custom tab components
import OverviewTab from "./components/OverviewTab";
import AllocationTab from "./components/AllocationTab";
import FuelPositionTab from "./components/FuelPositionTab";
import RegistryTab from "./components/RegistryTab";
import PlantStatusTab from "./components/PlantStatusTab";
import DailyFuelForm from "./components/DailyFuelForm";
import IppAgreementForm from "./components/IppAgreementForm";
import DocumentCenterTab from "./components/DocumentCenterTab";
import ReviewQueueTab from "./components/ReviewQueueTab";
import AuditLogTab from "./components/AuditLogTab";
import BackendStatusPanel from "./lib/BackendStatusPanel";
import { useLiveBackend } from "./lib/useLiveBackend";

// Import shared helpers and constants
import {
  inr, mt, shortPlant, currentAllocations, IPP_VC, HEAT_RATE, BLEND_GCV
} from "./lib/utils";

const TABS = [
  { id: "overview",     label: "Overview",       icon: "⚡" },
  { id: "allocation",   label: "Allocation",     icon: "📊" },
  { id: "daily",        label: "Fuel Position",  icon: "🛢️" },
  { id: "registry",     label: "ACQ Registry",   icon: "📋" },
  { id: "plantstatus",  label: "Plant Status",   icon: "🏭" },
  { id: "entry",        label: "Data Entry",     icon: "✏️" },
  { id: "documents",    label: "Document Centre",icon: "📁" },
  { id: "review",       label: "Review Queue",   icon: "📥" },
  { id: "audit",        label: "Audit Logs",     icon: "🛡️" },
];

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [tab, setTab] = useState("overview");
  const [showDetailsDrawer, setShowDetailsDrawer] = useState(false);
  const [snapshotData, setSnapshotData] = useState(snapshot);
  const [role, setRole] = useState("Fuel Cell Analyst");

  // Phase 1A: live backend data hook — independent of demoSnapshot
  const liveData = useLiveBackend();

  // Dynamic fetch of current backend snapshot
  const fetchSnapshot = async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/data/snapshot`);
      if (resp.ok) {
        const data = await resp.json();
        setSnapshotData(data);
      }
    } catch (err) {
      console.warn("FastAPI backend is offline or unreachable. Using demo data snapshot:", err.message);
    }
  };

  useEffect(() => {
    fetchSnapshot();
  }, []);

  const { optimization, daily_fuel, constraints, generated_from } = snapshotData;

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
  }, [recommendedAllocations]);

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
            <h1>Coal Optimization</h1>
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
        <div className="sidebar-footer" style={{ gap: 10, display: "flex", flexDirection: "column" }}>
          <div>
            <label className="form-label" style={{ fontSize: 10, color: "var(--ink-dim)", textTransform: "uppercase", letterSpacing: 0.5 }}>Simulated User Role</label>
            <select 
              value={role} 
              onChange={(e) => setRole(e.target.value)} 
              className="form-select" 
              style={{ fontSize: 11, background: "rgba(30,41,59,0.8)", border: "1px solid var(--border)", color: "var(--ink)" }}
            >
              <option>Plant Operator</option>
              <option>Fuel Cell Analyst</option>
              <option>Fuel Cell Approver</option>
              <option>Management User</option>
              <option>Auditor</option>
              <option>System Administrator</option>
            </select>
          </div>
          {/* ── Live backend status panel (Phase 0+) ── */}
          <BackendStatusPanel />
          {/* Sidebar optimization status pill — live backend only */}
          {
            liveData.connected === false ? (
              <div className="status-pill" style={{ background: "rgba(220,38,38,0.12)", color: "var(--coral)", borderColor: "rgba(220,38,38,0.3)" }}>
                BACKEND OFFLINE
              </div>
            ) : liveData.connected === null ? (
              <div className="status-pill" style={{ opacity: 0.5 }}>
                CONNECTING...
              </div>
            ) : liveData.dashboardSummary ? (
              <div
                className="status-pill"
                style={{
                  background: liveData.dashboardSummary.optimization.run_status === "COMPLETED"
                    ? "rgba(13,148,136,0.12)" : "rgba(220,38,38,0.10)",
                  color: liveData.dashboardSummary.optimization.run_status === "COMPLETED"
                    ? "var(--teal)" : "var(--coral)",
                  borderColor: liveData.dashboardSummary.optimization.run_status === "COMPLETED"
                    ? "rgba(13,148,136,0.35)" : "rgba(220,38,38,0.3)",
                }}
              >
                {liveData.dashboardSummary.optimization.latest_run_exists
                  ? liveData.dashboardSummary.optimization.run_status
                  : "NO RUN"}
              </div>
            ) : (
              <div className="status-pill" style={{ opacity: 0.5 }}>
                LOADING...
              </div>
            )
          }
          <div style={{ fontSize: 10, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", lineHeight: 1.5 }}>
            Report: 30 Jun 2026
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="main">
        {/* Topbar */}
        <div className="topbar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="topbar-title">
            {TABS.find((t) => t.id === tab)?.label}
          </div>
          <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
            {/* Topbar run status — derived from live backend only, never from demo snapshot */}
            <div className="topbar-meta">
              <span>Run status:</span>
              {
                liveData.connected === false ? (
                  <span className="run-badge" style={{ background: "rgba(220,38,38,0.12)", color: "var(--coral)", border: "1px solid rgba(220,38,38,0.3)" }}>BACKEND OFFLINE</span>
                ) : liveData.connected === null || !liveData.dashboardSummary ? (
                  <span className="run-badge" style={{ opacity: 0.5 }}>Loading...</span>
                ) : !liveData.dashboardSummary.optimization.latest_run_exists ? (
                  <span className="run-badge" style={{ background: "rgba(148,163,184,0.10)", color: "var(--ink-dim)", border: "1px solid rgba(148,163,184,0.3)" }}>NO RUN</span>
                ) : liveData.dashboardSummary.optimization.run_status === "COMPLETED" ? (
                  <span className="run-badge" style={{ background: "rgba(13,148,136,0.12)", color: "var(--teal)", border: "1px solid rgba(13,148,136,0.35)" }}>COMPLETED</span>
                ) : (
                  <span className="run-badge" style={{ background: "rgba(220,38,38,0.10)", color: "var(--coral)", border: "1px solid rgba(220,38,38,0.3)" }}>
                    {liveData.dashboardSummary.optimization.run_status}
                  </span>
                )
              }
              <span style={{ color: "var(--ink-dim)" }}>|</span>
              {
                liveData.connected === false ? (
                  <span style={{ color: "var(--ink-dim)" }}>— plants</span>
                ) : liveData.dashboardSummary?.optimization?.latest_run_exists ? (
                  <span>{liveData.dashboardSummary.optimization.plants_covered_count} plants covered</span>
                ) : (
                  <span style={{ color: "var(--ink-dim)" }}>—</span>
                )
              }
            </div>
            {["Fuel Cell Analyst", "Fuel Cell Approver", "System Administrator"].includes(role) && (
              <button 
                className="submit-btn" 
                style={{ padding: "6px 14px", fontSize: "12px", background: "var(--teal)" }}
                onClick={() => setTab("allocation")}
              >
                ⚡ Run Optimization
              </button>
            )}
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

        {/* Tab rendering */}
        {tab === "overview" && (
          <OverviewTab
            optimization={optimization}
            daily_fuel={daily_fuel}
            constraints={constraints}
            setShowDetailsDrawer={setShowDetailsDrawer}
            liveData={liveData}
          />
        )}

        {tab === "allocation" && (
          <AllocationTab
            optimization={optimization}
            setShowDetailsDrawer={setShowDetailsDrawer}
            liveData={liveData}
          />
        )}

        {tab === "daily" && (
          <FuelPositionTab daily_fuel={daily_fuel} liveData={liveData} />
        )}

        {tab === "registry" && (
          <RegistryTab constraints={constraints} />
        )}

        {tab === "plantstatus" && (
          <PlantStatusTab
            optimization={optimization}
            daily_fuel={daily_fuel}
            setShowDetailsDrawer={setShowDetailsDrawer}
            liveData={liveData}
          />
        )}

        {tab === "entry" && (
          <div className="page-content" id="tab-entry">
            <p className="section-intro">
              Manage operational fuel inputs and variable cost tie-up agreements with Independent Power Producers (IPPs).
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1.8fr", gap: "28px", alignItems: "start" }}>
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Daily Fuel Entry Form</span>
                  <span className="panel-badge amber">Manual Input</span>
                </div>
                <DailyFuelForm refreshLive={liveData.refresh} />
              </div>
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

        {tab === "documents" && (
          <DocumentCenterTab role={role} refreshLive={liveData.refresh} />
        )}

        {tab === "review" && (
          <ReviewQueueTab role={role} refreshLive={liveData.refresh} />
        )}

        {tab === "audit" && (
          <AuditLogTab />
        )}

        {/* Footer */}
        <div className="dash-footer">
          Data source: {generated_from} · Zero-Recurring-Cost Office Ingestion Pipeline
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
