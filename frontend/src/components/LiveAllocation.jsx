/**
 * LiveAllocation.jsx
 *
 * Read-only live allocation panel for the Allocation tab + Pre-Run Controller.
 * Phase 2B — connects to:
 *   GET /api/v1/validation/summary                       (Precheck)
 *   POST /api/v1/optimization/run                        (Trigger)
 *   GET /api/v1/optimization/latest                      (Run details)
 *   GET /api/v1/optimization/runs/{run_id}/allocations  (only when COMPLETED)
 *   GET /api/v1/plants                                   (UUID -> name resolution)
 *
 * States handled:
 *   A. COMPLETED  → allocation table with plant name, type, qty, unit cost, est. cost
 *   B. INCOMPLETE → status + validation reasons, guidance message, no fake allocations
 *   C. No run     → "No optimization run available yet"
 *   D. FAILED     → run failed message
 *   E. Offline    → BACKEND OFFLINE banner, no crash
 */

import React, { useState, useMemo } from "react";
import { apiUrl } from "../lib/api";

// ── Helpers ──────────────────────────────────────────────────────────────────

function inrCr(val) {
  if (val == null || isNaN(val)) return "—";
  return "₹" + (Number(val) / 1e7).toFixed(2) + " Cr";
}

function fmtMT(val) {
  if (val == null || isNaN(val)) return "—";
  const n = Number(val);
  if (n >= 1000) return (n / 1000).toFixed(1) + "k MT";
  return n.toFixed(0) + " MT";
}

function inrMT(val) {
  if (val == null || isNaN(val)) return "—";
  return "₹" + Number(val).toLocaleString("en-IN", { maximumFractionDigits: 0 }) + "/MT";
}

// ── Badges ────────────────────────────────────────────────────────────────────

const BADGE_STYLES = {
  "LIVE BACKEND DATA":    { bg: "rgba(13,148,136,0.09)", border: "rgba(13,148,136,0.30)", text: "var(--teal)" },
  "DEMO DATA":            { bg: "rgba(124,58,237,0.09)", border: "rgba(124,58,237,0.25)", text: "var(--violet)" },
  "BACKEND OFFLINE":      { bg: "rgba(220,38,38,0.08)", border: "rgba(220,38,38,0.25)", text: "var(--coral)" },
  "OPTIMIZATION INCOMPLETE": { bg: "rgba(220,38,38,0.08)", border: "rgba(220,38,38,0.25)", text: "var(--coral)" },
  "NO LIVE DATA":         { bg: "rgba(148,163,184,0.10)", border: "rgba(148,163,184,0.30)", text: "var(--ink-dim)" },
  READY:                  { bg: "rgba(13,148,136,0.12)", border: "rgba(13,148,136,0.35)", text: "var(--teal)" },
  WARNING:                { bg: "rgba(217,119,6,0.10)",  border: "rgba(217,119,6,0.30)",  text: "var(--amber)" },
  INCOMPLETE:             { bg: "rgba(220,38,38,0.10)",  border: "rgba(220,38,38,0.30)",  text: "var(--coral)" },
  RUNNING:                { bg: "rgba(2,132,199,0.10)",  border: "rgba(2,132,199,0.30)",  text: "var(--sky)" },
  FAILED:                 { bg: "rgba(220,38,38,0.10)",  border: "rgba(220,38,38,0.30)",  text: "var(--coral)" },
};

function Badge({ label }) {
  const key = label.toUpperCase();
  const s = BADGE_STYLES[key] || BADGE_STYLES["NO LIVE DATA"];
  return (
    <span
      style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        padding: "3px 9px", borderRadius: 20, background: s.bg,
        border: `1.5px solid ${s.border}`, color: s.text,
        fontSize: 9, fontWeight: 700, fontFamily: "var(--font-mono)",
        letterSpacing: "0.08em", textTransform: "uppercase",
        whiteSpace: "nowrap"
      }}
    >
      {key === "LIVE BACKEND DATA" && (
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: s.text, display: "inline-block", animation: "pulse-dot 2s ease infinite" }} />
      )}
      {label}
    </span>
  );
}

// ── Issue chip ────────────────────────────────────────────────────────────────

function IssueLine({ issue }) {
  const col = issue.severity === "CRITICAL" ? "var(--coral)" : issue.severity === "WARNING" ? "var(--amber)" : "var(--ink-dim)";
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-start", padding: "5px 8px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6 }}>
      <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", fontWeight: 700, color: col, flexShrink: 0, paddingTop: 2, textTransform: "uppercase" }}>
        {issue.severity}
      </span>
      <span style={{ fontSize: 11, color: "var(--ink-muted)", lineHeight: 1.4 }}>{issue.message}</span>
    </div>
  );
}

// ── Allocation type label ─────────────────────────────────────────────────────

function typeLabel(allocationType) {
  if (!allocationType) return "—";
  if (allocationType === "fsa") return "FSA";
  if (allocationType === "bridge_linkage") return "Bridge";
  if (allocationType === "market_topup") return "Market";
  return allocationType.replace(/_/g, " ").toUpperCase();
}

function typeColor(allocationType) {
  if (allocationType === "market_topup") return "var(--coral)";
  if (allocationType === "bridge_linkage") return "var(--amber)";
  return "var(--teal)";
}

// ── Main component ────────────────────────────────────────────────────────────

export default function LiveAllocation({ liveData }) {
  const { connected, validation, optimization, allocations, plants, loading, refresh, lastRefresh } = liveData;

  const [running, setRunning] = useState(false);
  const [triggerError, setTriggerError] = useState(null);

  // Build UUID → plant name map
  const plantMap = useMemo(() => {
    if (!plants) return {};
    return Object.fromEntries(plants.map((p) => [p.id, p.plant_name]));
  }, [plants]);

  const isOffline = connected === false;
  const isProbing = connected === null;
  const runStatus = (optimization?.status ?? "").toUpperCase();
  const hasRun = optimization != null;

  // Pre-Run Validation details
  const valStatus = validation?.overall_status ?? "INCOMPLETE";
  const totalIssues = validation?.total_issues ?? 0;
  const criticalCount = validation?.issues?.filter(i => i.severity === "CRITICAL").length ?? 0;
  const warningCount = validation?.issues?.filter(i => i.severity === "WARNING").length ?? 0;

  const precheckBlockers = useMemo(() => {
    if (!validation?.issues) return [];
    return validation.issues.slice(0, 4);
  }, [validation]);

  // Trigger POST /api/v1/optimization/run
  const handleRunOptimization = async () => {
    if (running || isOffline) return;
    setRunning(true);
    setTriggerError(null);

    try {
      const resp = await fetch(apiUrl("/optimization/run"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify({ triggered_by: "manual" })
      });

      if (!resp.ok) {
        throw new Error(`Server returned HTTP ${resp.status}`);
      }

      const result = await resp.json();
      
      // Refresh the main liveData hook to reload results
      if (refresh) {
        await refresh();
      }
    } catch (err) {
      console.error(err);
      setTriggerError("Optimization could not be completed. Please review the input status and try again.");
    } finally {
      setRunning(false);
    }
  };

  // Determine panel badge
  const panelBadge = isOffline
    ? "BACKEND OFFLINE"
    : running
    ? "RUNNING"
    : !hasRun
    ? "NO LIVE DATA"
    : runStatus === "COMPLETED"
    ? "LIVE BACKEND DATA"
    : runStatus === "INCOMPLETE" || runStatus === "FAILED"
    ? "OPTIMIZATION INCOMPLETE"
    : "NO LIVE DATA";

  // Aggregate allocation rows by plant for the table
  const allocationsByPlant = useMemo(() => {
    if (!allocations || allocations.length === 0) return [];
    const byPlant = {};
    allocations.forEach((a) => {
      const name = plantMap[a.plant_id] || a.plant_id;
      if (!byPlant[name]) byPlant[name] = [];
      byPlant[name].push(a);
    });
    return Object.entries(byPlant)
      .map(([name, rows]) => ({ plantName: name, rows }))
      .sort((a, b) => a.plantName.localeCompare(b.plantName));
  }, [allocations, plantMap]);

  const totalCost = optimization?.total_estimated_cost ?? null;
  const runTs = optimization?.run_timestamp
    ? new Date(optimization.run_timestamp).toLocaleString("en-IN", {
        day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit", hour12: false
      })
    : null;

  // Incomplete reasons from run's stored validation_summary
  const incompleteReasons = useMemo(() => {
    if (runStatus !== "INCOMPLETE" && runStatus !== "FAILED") return [];
    const stored = optimization?.validation_summary;
    if (!stored?.issues) return [];
    return stored.issues.slice(0, 5);
  }, [optimization, runStatus]);

  const refreshTs = lastRefresh
    ? lastRefresh.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })
    : null;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      
      {/* ── SECTION 1: Optimization Pre-Run & Action Controller ── */}
      <div className="panel" id="optimization-precheck-panel">
        <div className="panel-header">
          <span className="panel-title">Optimization Readiness Precheck</span>
          <Badge label={isOffline ? "BACKEND OFFLINE" : running ? "RUNNING" : valStatus} />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {isOffline ? (
            <div style={{ fontSize: 12, color: "var(--coral)", fontFamily: "var(--font-mono)" }}>
              ⚠️ Precheck unavailable. Backend is offline.
            </div>
          ) : (
            <>
              {/* Readiness status details */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>
                    {valStatus === "READY" && "✓ System Ready"}
                    {valStatus === "WARNING" && "⚠ System Warning"}
                    {valStatus === "INCOMPLETE" && "❌ Operational Inputs Incomplete"}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 2 }}>
                    {valStatus === "READY" && "All mandatory data entries and landed costs are approved."}
                    {valStatus === "WARNING" && "Non-critical issues present. Optimization can still run."}
                    {valStatus === "INCOMPLETE" && "Critical data gaps exist. Optimization solver might yield incomplete results."}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink)" }}>
                    Critical: <strong style={{ color: "var(--coral)" }}>{criticalCount}</strong> | Warnings: <strong style={{ color: "var(--amber)" }}>{warningCount}</strong>
                  </div>
                </div>
              </div>

              {/* Bulleted list of blocker issues */}
              {precheckBlockers.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <span style={{ fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                    Blocker List (Top {precheckBlockers.length})
                  </span>
                  {precheckBlockers.map((issue, i) => (
                    <IssueLine key={i} issue={issue} />
                  ))}
                </div>
              )}

              {/* Guidance for incomplete state */}
              {valStatus === "INCOMPLETE" && (
                <div style={{
                  padding: "8px 12px", background: "rgba(220,38,38,0.05)", border: "1px solid rgba(220,38,38,0.18)",
                  borderRadius: 8, fontSize: 11, color: "var(--coral)", lineHeight: 1.4
                }}>
                  ⚠️ <strong>Notice:</strong> Operational inputs are missing or pending review. The backend may store this run as <strong>INCOMPLETE</strong> and will not output recommended allocations.
                </div>
              )}
            </>
          )}

          {/* Action button row */}
          <div style={{ display: "flex", gap: 14, alignItems: "center", marginTop: 4, paddingTop: 10, borderTop: "1px solid var(--border)" }}>
            <button
              id="btn-trigger-optimization"
              className="submit-btn"
              style={{
                margin: 0, padding: "10px 22px", width: "auto",
                background: running
                  ? "var(--border)"
                  : isOffline
                  ? "var(--bg-2)"
                  : valStatus === "INCOMPLETE"
                  ? "linear-gradient(135deg, var(--coral), #f87171)"
                  : "linear-gradient(135deg, var(--teal), #2dd4bf)",
                boxShadow: running || isOffline ? "none" : "",
                cursor: running || isOffline ? "not-allowed" : "pointer"
              }}
              disabled={running || isOffline}
              onClick={handleRunOptimization}
            >
              {running ? "⏳ Running optimization…" : "⚡ Run Optimization"}
            </button>

            {running && (
              <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--sky)" }}>
                Solving procurement LP optimization problem…
              </span>
            )}
          </div>

          {/* Error notification banner */}
          {triggerError && (
            <div style={{
              background: "rgba(220,38,38,0.06)", border: "1.5px solid rgba(220,38,38,0.20)",
              borderRadius: 8, padding: "10px 14px", display: "flex", justifyContent: "space-between", alignItems: "center"
            }}>
              <span style={{ fontSize: 11, color: "var(--coral)", lineHeight: 1.4 }}>{triggerError}</span>
              <button
                onClick={handleRunOptimization}
                style={{
                  background: "var(--coral)", color: "#fff", border: "none", borderRadius: 4,
                  padding: "3px 8px", cursor: "pointer", fontSize: 10, fontFamily: "var(--font-mono)"
                }}
              >
                Retry
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ── SECTION 2: Optimization Results Viewer ── */}
      <div className="panel" id="live-allocation">
        <div className="panel-header">
          <span className="panel-title" style={{ display: "flex", alignItems: "center", gap: 10 }}>
            Allocation Results
            <Badge label={panelBadge} />
          </span>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {refreshTs && (
              <span style={{ fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-mono)" }}>{refreshTs}</span>
            )}
            <button
              id="btn-refresh-allocation"
              onClick={refresh}
              disabled={running}
              style={{
                background: "var(--bg)", border: "1.5px solid var(--border)",
                borderRadius: 8, padding: "4px 10px", cursor: "pointer",
                fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-muted)",
                fontWeight: 600, display: "flex", alignItems: "center", gap: 4,
              }}
            >
              ↻ Refresh
            </button>
          </div>
        </div>

        {/* ── State A: BACKEND OFFLINE ────────────────────────────────────── */}
        {isOffline && (
          <div style={{
            background: "rgba(220,38,38,0.05)", border: "1.5px solid rgba(220,38,38,0.18)",
            borderRadius: 8, padding: "12px 16px"
          }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--coral)", fontFamily: "var(--font-mono)" }}>Backend Offline</div>
            <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 2 }}>
              Optimization was not started because the backend is unavailable. Live results cannot be fetched.
            </div>
          </div>
        )}

        {/* ── State: Initial probe / loading ─────────────────────────────── */}
        {isProbing && (
          <div style={{ padding: "20px 0", textAlign: "center", color: "var(--ink-dim)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
            Connecting to backend…
          </div>
        )}

        {/* ── State C: No run exists ──────────────────────────────────────── */}
        {!isOffline && !isProbing && !hasRun && (
          <div style={{
            padding: "24px 16px", textAlign: "center", display: "flex",
            flexDirection: "column", alignItems: "center", gap: 8
          }}>
            <span style={{ fontSize: 28 }}>📊</span>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink-muted)" }}>No optimization run available yet.</div>
            <div style={{ fontSize: 11, color: "var(--ink-dim)", maxWidth: 420, lineHeight: 1.5 }}>
              Trigger an optimization run above once all required operational inputs have been entered and approved.
            </div>
          </div>
        )}

        {/* ── State B/D: INCOMPLETE or FAILED ────────────────────────────── */}
        {!isOffline && !isProbing && hasRun && runStatus !== "COMPLETED" && (
          <div>
            <div style={{
              background: "rgba(220,38,38,0.05)", border: "1.5px solid rgba(220,38,38,0.18)",
              borderRadius: 8, padding: "12px 16px", marginBottom: 12,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                <span style={{ fontSize: 16 }}>
                  {runStatus === "FAILED" ? "❌" : "⚠️"}
                </span>
                <span style={{ fontSize: 12, fontWeight: 700, color: "var(--coral)", fontFamily: "var(--font-mono)" }}>
                  OPTIMIZATION {runStatus}
                </span>
                {runTs && (
                  <span style={{ fontSize: 10, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", marginLeft: "auto" }}>
                    Run: {runTs}
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-muted)", lineHeight: 1.5 }}>
                {runStatus === "FAILED"
                  ? "The last optimization run encountered an error. Check backend logs for details."
                  : "The last optimization run could not generate an allocation because required input data is missing or invalid."}
              </div>
              {optimization?.notes && (
                <div style={{ marginTop: 6, fontSize: 10, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", borderTop: "1px solid var(--border)", paddingTop: 6 }}>
                  {optimization.notes}
                </div>
              )}
            </div>

            {incompleteReasons.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 10, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>
                  Run Blocker reasons
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {incompleteReasons.map((issue, i) => <IssueLine key={i} issue={issue} />)}
                </div>
              </div>
            )}

            <div style={{
              background: "rgba(217,119,6,0.06)", border: "1px solid rgba(217,119,6,0.20)",
              borderRadius: 8, padding: "10px 14px", fontSize: 11, color: "var(--amber)", lineHeight: 1.5
            }}>
              <strong>Action required:</strong> Complete or approve the required operational inputs, then run optimization again.
            </div>
          </div>
        )}

        {/* ── State A: COMPLETED ─────────────────────────────────────────── */}
        {!isOffline && !isProbing && hasRun && runStatus === "COMPLETED" && (
          <div>
            {/* Summary metrics row */}
            <div style={{
              display: "flex", gap: 20, flexWrap: "wrap", padding: "10px 0 14px",
              borderBottom: "1px solid var(--border)", marginBottom: 14,
            }}>
              <div>
                <div style={{ fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.07em" }}>Run Time</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink)", fontFamily: "var(--font-mono)" }}>{runTs || "—"}</div>
              </div>
              <div>
                <div style={{ fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.07em" }}>Total Est. Cost</div>
                <div style={{ fontSize: 15, fontWeight: 800, color: "var(--amber)", fontFamily: "var(--font-mono)" }}>{inrCr(totalCost)}</div>
              </div>
              <div>
                <div style={{ fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.07em" }}>Allocation Lines</div>
                <div style={{ fontSize: 12, fontWeight: 700, color: "var(--ink)", fontFamily: "var(--font-mono)" }}>{allocations?.length ?? "—"}</div>
              </div>
              <div>
                <div style={{ fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.07em" }}>Market Top-Up</div>
                <div style={{ fontSize: 11, fontWeight: 700, fontFamily: "var(--font-mono)" }}>
                  {allocations?.some(a => a.allocation_type === "market_topup")
                    ? <span style={{ color: "var(--coral)" }}>⚠ Required</span>
                    : <span style={{ color: "var(--teal)" }}>✓ None</span>}
                </div>
              </div>
            </div>

            {/* Per-plant allocation tables */}
            {allocationsByPlant.length === 0 ? (
              <div style={{ padding: "16px 0", textAlign: "center", color: "var(--ink-dim)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                No allocation rows returned. The run may have produced an empty allocation.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {allocationsByPlant.map(({ plantName, rows }) => {
                  const totalQty = rows.reduce((s, r) => s + (r.quantity_mt || 0), 0);
                  const totalEst = rows.reduce((s, r) => s + (r.estimated_cost || 0), 0);
                  const hasTopup = rows.some(r => r.allocation_type === "market_topup");
                  return (
                    <div key={plantName} className="plant-alloc-card">
                      <div className="plant-alloc-header">
                        <span className="plant-alloc-name">🏭 {plantName}</span>
                        <span className="plant-alloc-total">
                          Total: {fmtMT(totalQty)} | Est: {inrCr(totalEst)}
                          {hasTopup && <span style={{ color: "var(--coral)", marginLeft: 8 }}>⚠ Market top-up</span>}
                        </span>
                      </div>
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Type</th>
                            <th>Quantity (MT)</th>
                            <th>Unit Cost (₹/MT)</th>
                            <th>Est. Cost</th>
                            <th>ACQ Utilisation</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map((r, i) => (
                            <tr key={i}>
                              <td>
                                <span style={{
                                  fontSize: 10, fontWeight: 700, fontFamily: "var(--font-mono)",
                                  color: typeColor(r.allocation_type),
                                  background: "var(--bg)", border: "1px solid var(--border)",
                                  borderRadius: 4, padding: "2px 7px",
                                }}>
                                  {typeLabel(r.allocation_type)}
                                </span>
                              </td>
                              <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{fmtMT(r.quantity_mt)}</td>
                              <td style={{ fontFamily: "var(--font-mono)" }}>{inrMT(r.unit_cost)}</td>
                              <td style={{ fontFamily: "var(--font-mono)", color: "var(--amber)", fontWeight: 700 }}>{inrCr(r.estimated_cost)}</td>
                              <td>
                                {r.acq_utilization_pct != null ? (
                                  <div className="util-wrap">
                                    <div className="util-track">
                                      <div
                                        className={`util-fill${r.acq_utilization_pct > 100 ? " over" : ""}`}
                                        style={{ width: Math.min(100, r.acq_utilization_pct) + "%" }}
                                      />
                                    </div>
                                    <span className="util-pct">{r.acq_utilization_pct.toFixed(1)}%</span>
                                  </div>
                                ) : (
                                  <span style={{ color: "var(--ink-dim)", fontFamily: "var(--font-mono)", fontSize: 11 }}>—</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

    </div>
  );
}
