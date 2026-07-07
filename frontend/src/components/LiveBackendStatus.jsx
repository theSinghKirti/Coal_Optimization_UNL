import React, { useState } from "react";

// ── Formatting helpers ───────────────────────────────────────────────────────

function fmtCost(val) {
  if (val == null || isNaN(val)) return "—";
  if (val >= 1e7) return "₹" + (val / 1e7).toFixed(2) + " Cr";
  if (val >= 1e5) return "₹" + (val / 1e5).toFixed(2) + " L";
  return "₹" + Math.round(val).toLocaleString("en-IN");
}

function fmtQty(val) {
  if (val == null || isNaN(val)) return "—";
  return new Intl.NumberFormat("en-IN").format(Math.round(val)) + " MT";
}

function fmtTs(ts) {
  if (!ts) return "—";
  try {
    const d = new Date(ts);
    if (isNaN(d)) return "—";
    return d.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return "—";
  }
}

// ── Custom subcomponents ─────────────────────────────────────────────────────

const BADGE_STYLES = {
  READY:       { bg: "rgba(13,148,136,0.12)", border: "rgba(13,148,136,0.35)", color: "var(--teal)" },
  WARNING:     { bg: "rgba(217,119,6,0.10)",  border: "rgba(217,119,6,0.30)",  color: "var(--amber)" },
  INCOMPLETE:  { bg: "rgba(220,38,38,0.10)",  border: "rgba(220,38,38,0.30)",  color: "var(--coral)" },
  CRITICAL:    { bg: "rgba(220,38,38,0.10)",  border: "rgba(220,38,38,0.30)",  color: "var(--coral)" },
  INFO:        { bg: "rgba(59,130,246,0.10)",  border: "rgba(59,130,246,0.30)",  color: "var(--sky)" },
  LIVE:        { bg: "rgba(13,148,136,0.12)", border: "rgba(13,148,136,0.35)", color: "var(--teal)" },
  OFFLINE:     { bg: "rgba(220,38,38,0.10)",  border: "rgba(220,38,38,0.30)",  color: "var(--coral)" },
  COMPLETED:   { bg: "rgba(13,148,136,0.12)", border: "rgba(13,148,136,0.35)", color: "var(--teal)" },
  "NO RUN":    { bg: "rgba(148,163,184,0.10)", border: "rgba(148,163,184,0.3)",  color: "var(--ink-dim)" },
};

function StatusBadge({ label }) {
  const key = (label || "").toUpperCase();
  const s = BADGE_STYLES[key] || BADGE_STYLES["NO RUN"];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "3px 10px",
        borderRadius: 20,
        background: s.bg,
        border: `1.5px solid ${s.border}`,
        color: s.color,
        fontSize: 10,
        fontWeight: 700,
        fontFamily: "var(--font-mono)",
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}

function CoverageRow({ label, value, sub = null }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", borderBottom: "1px solid rgba(255,255,255,0.03)", padding: "5px 0" }}>
      <span style={{ fontSize: 12, color: "var(--ink-dim)" }}>{label}</span>
      <div style={{ textAlign: "right" }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--ink)" }}>{value}</span>
        {sub && <div style={{ fontSize: 9, color: "var(--ink-muted)", marginTop: 1 }}>{sub}</div>}
      </div>
    </div>
  );
}

function BlockerItem({ blocker }) {
  const isCrit = blocker.severity === "CRITICAL";
  return (
    <div style={{
      display: "flex",
      gap: 10,
      padding: "8px 12px",
      borderRadius: 6,
      background: isCrit ? "rgba(220,38,38,0.04)" : "rgba(217,119,6,0.04)",
      border: `1.5px solid ${isCrit ? "rgba(220,38,38,0.15)" : "rgba(217,119,6,0.15)"}`,
      marginBottom: 6,
    }}>
      <span style={{ color: isCrit ? "var(--coral)" : "var(--amber)", fontSize: 13 }}>⚠️</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: isCrit ? "var(--coral)" : "var(--amber)" }}>
          {blocker.category.replace("_", " ")} ({blocker.code})
        </div>
        <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 2 }}>{blocker.message}</div>
        {blocker.affected_plant_count != null && blocker.affected_plant_count > 0 && (
          <div style={{ fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-mono)", marginTop: 2 }}>
            Affects {blocker.affected_plant_count} plant(s)
          </div>
        )}
      </div>
    </div>
  );
}

function RecommendationCard({ rec }) {
  const [open, setOpen] = useState(false);
  const isCrit = rec.severity === "CRITICAL";
  const isWarn = rec.severity === "WARNING";
  const icon = isCrit ? "🚨" : isWarn ? "⚠️" : "💡";
  const severityColor = isCrit ? "var(--coral)" : isWarn ? "var(--amber)" : "var(--sky)";

  return (
    <div style={{
      padding: 16,
      borderRadius: 8,
      background: "rgba(30,41,59,0.3)",
      border: `1.5px solid ${isCrit ? "rgba(220,38,38,0.2)" : "rgba(255,255,255,0.06)"}`,
      marginBottom: 12,
      transition: "border 0.2s ease",
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{ fontSize: 16 }}>{icon}</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)" }}>{rec.title}</div>
            <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--ink-dim)", marginTop: 2, display: "flex", gap: 8, textTransform: "uppercase" }}>
              <span>{rec.category.replace("_", " ")}</span>
              <span>•</span>
              <span>{rec.related_module}</span>
            </div>
          </div>
        </div>
        <StatusBadge label={rec.severity} />
      </div>

      {/* Message */}
      <div style={{ fontSize: 12, color: "var(--ink-muted)", marginTop: 8, lineHeight: 1.5 }}>
        {rec.message}
      </div>

      {/* Next Action Box */}
      <div style={{
        marginTop: 12,
        padding: "8px 12px",
        borderRadius: 6,
        background: "rgba(255,255,255,0.02)",
        borderLeft: `3px solid ${severityColor}`,
      }}>
        <div style={{ fontSize: 10, color: "var(--ink-dim)", textTransform: "uppercase", letterSpacing: 0.5 }}>Recommended Action</div>
        <div style={{ fontSize: 12, color: "var(--ink)", fontWeight: 600, marginTop: 2 }}>{rec.recommended_next_action}</div>
      </div>

      {/* Details Box Toggle */}
      <div style={{ marginTop: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        {rec.affected_plant_name && (
          <span style={{ fontSize: 11, color: "var(--ink-dim)", fontFamily: "var(--font-mono)" }}>
            Plant: {rec.affected_plant_name}
          </span>
        )}
        <button
          onClick={() => setOpen(!open)}
          style={{
            background: "none",
            border: "none",
            color: "var(--teal)",
            cursor: "pointer",
            fontSize: 11,
            fontFamily: "var(--font-mono)",
            fontWeight: 700,
            padding: 0,
          }}
        >
          {open ? "▲ Hide Traceability Details" : "▼ Show Traceability Details"}
        </button>
      </div>

      {open && (
        <div style={{
          marginTop: 12,
          padding: 10,
          background: "rgba(15,23,42,0.6)",
          border: "1px dashed var(--border)",
          borderRadius: 6,
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          color: "var(--ink-muted)",
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}>
          <div><strong>Stable Key:</strong> {rec.recommendation_key}</div>
          {rec.source_entity_type && <div><strong>Source Entity:</strong> {rec.source_entity_type}</div>}
          {rec.source_entity_ids && rec.source_entity_ids.length > 0 && (
            <div><strong>Source Entity ID(s):</strong> {rec.source_entity_ids.join(", ")}</div>
          )}
          {rec.optimization_run_id && <div><strong>Optimization Run ID:</strong> {rec.optimization_run_id}</div>}
          {rec.status_context && <div><strong>Context:</strong> {rec.status_context}</div>}
          {rec.created_from_data_as_of && <div><strong>Data As Of:</strong> {rec.created_from_data_as_of}</div>}
        </div>
      )}
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export default function LiveBackendStatus({ liveData }) {
  const {
    loading,
    connected,
    dashboardSummary,
    latestRecommendations,
    lastRefresh,
    refresh,
  } = liveData;

  const isOffline = connected === false;
  const isProbing = connected === null;

  const refreshTime = lastRefresh
    ? lastRefresh.toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      })
    : null;

  return (
    <div style={{ width: "100%", marginBottom: 28 }} id="live-backend-status">
      {/* Title block */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <h2 style={{ fontSize: 16, margin: 0, fontWeight: 700, color: "var(--ink)" }}>Live Operational Summary</h2>
          <StatusBadge label={isOffline ? "OFFLINE" : isProbing ? "NO RUN" : "LIVE"} />
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {refreshTime && (
            <span style={{ fontSize: 10, color: "var(--ink-dim)", fontFamily: "var(--font-mono)" }}>
              Refreshed: {refreshTime}
            </span>
          )}
          <button
            onClick={refresh}
            disabled={loading}
            style={{
              background: "rgba(15,23,42,0.8)",
              border: "1.5px solid var(--border)",
              borderRadius: 6,
              color: "var(--ink)",
              padding: "4px 10px",
              cursor: "pointer",
              fontSize: 11,
              fontWeight: 600,
            }}
          >
            {loading ? "🔄 Updating..." : "🔄 Refresh"}
          </button>
        </div>
      </div>

      {/* Offline banner */}
      {isOffline && (
        <div style={{
          background: "rgba(220,38,38,0.06)",
          border: "1.5px solid rgba(220,38,38,0.22)",
          borderRadius: 8,
          padding: 12,
          marginBottom: 20,
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}>
          <span style={{ fontSize: 18 }}>⚠️</span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--coral)", fontFamily: "var(--font-mono)" }}>
              BACKEND OFFLINE
            </div>
            <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 2 }}>
              Live operational data is currently unavailable. Displaying cached demo dashboard visualizations.
            </div>
          </div>
        </div>
      )}

      {/* Live contents grid */}
      {!isOffline && dashboardSummary && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          
          {/* Section: Operational Readiness */}
          <div className="panel" style={{ padding: 18 }}>
            <div className="panel-header" style={{ marginBottom: 14 }}>
              <span className="panel-title">Operational Readiness</span>
              <span className="panel-badge teal">LIVE BACKEND DATA</span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 20 }}>
              {/* Card 1: System & Validation */}
              <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: 6, padding: 12 }}>
                <div style={{ fontSize: 10, color: "var(--ink-dim)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>Readiness Status</div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <StatusBadge label={dashboardSummary.metadata.system_status} />
                  <span style={{ fontSize: 11, color: "var(--ink-dim)", fontFamily: "var(--font-mono)" }}>
                    {dashboardSummary.validation.total_issue_count} issues
                  </span>
                </div>
                
                {/* Issue counts breakdown */}
                <div style={{ fontSize: 11, color: "var(--ink-muted)", display: "flex", flexDirection: "column", gap: 4 }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Critical Blockers:</span>
                    <span style={{ fontWeight: 700, color: dashboardSummary.validation.critical_issue_count > 0 ? "var(--coral)" : "var(--ink-dim)" }}>
                      {dashboardSummary.validation.critical_issue_count}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Warnings:</span>
                    <span style={{ fontWeight: 700, color: "var(--amber)" }}>
                      {dashboardSummary.validation.warning_issue_count}
                    </span>
                  </div>
                </div>

                {/* Top Blockers list */}
                {dashboardSummary.validation.top_blockers.length > 0 && (
                  <div style={{ marginTop: 12, borderTop: "1px dashed var(--border)", paddingTop: 8 }}>
                    <div style={{ fontSize: 9, color: "var(--ink-dim)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>Top Blocker Notes</div>
                    {dashboardSummary.validation.top_blockers.slice(0, 3).map((b, idx) => (
                      <BlockerItem key={idx} blocker={b} />
                    ))}
                  </div>
                )}
              </div>

              {/* Card 2: Daily Stock */}
              <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: 6, padding: 12 }}>
                <div style={{ fontSize: 10, color: "var(--ink-dim)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>Daily Stock Coverage</div>
                
                <CoverageRow label="Active Plants" value={dashboardSummary.coverage.daily_stock.total_active_plants} />
                <CoverageRow label="With Latest Stock" value={dashboardSummary.coverage.daily_stock.plants_with_latest_daily_stock} />
                <CoverageRow 
                  label="Missing Stock" 
                  value={dashboardSummary.coverage.daily_stock.plants_missing_latest_daily_stock} 
                  sub={dashboardSummary.coverage.daily_stock.plants_missing_latest_daily_stock > 0 ? "Blocker" : null}
                />
                <CoverageRow 
                  label="Latest Stock Date" 
                  value={dashboardSummary.coverage.daily_stock.latest_daily_stock_date || "—"} 
                />
              </div>

              {/* Card 3: FSA Constraints */}
              <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: 6, padding: 12 }}>
                <div style={{ fontSize: 10, color: "var(--ink-dim)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>FSA / Bridge Coverage</div>
                
                <CoverageRow label="Approved Active" value={dashboardSummary.coverage.fsa_constraint.approved_active_constraint_count} />
                <CoverageRow label="Pending Review" value={dashboardSummary.coverage.fsa_constraint.pending_review_constraint_count} />
                <CoverageRow 
                  label="Unmapped Constraints" 
                  value={dashboardSummary.coverage.fsa_constraint.unmapped_constraint_count} 
                  sub={dashboardSummary.coverage.fsa_constraint.unmapped_constraint_count > 0 ? "Blocker" : null}
                />
                <CoverageRow label="Rejected Count" value={dashboardSummary.coverage.fsa_constraint.rejected_constraint_count} />
              </div>

              {/* Card 4: Landed Costs */}
              <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: 6, padding: 12 }}>
                <div style={{ fontSize: 10, color: "var(--ink-dim)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>Landed Cost Coverage</div>
                
                <CoverageRow label="Approved Active" value={dashboardSummary.coverage.landed_cost.approved_active_landed_cost_count} />
                <CoverageRow label="Pending Review" value={dashboardSummary.coverage.landed_cost.pending_review_landed_cost_count} />
                <CoverageRow label="Needs Review" value={dashboardSummary.coverage.landed_cost.needs_review_landed_cost_count} />
                <CoverageRow 
                  label="Missing Plant Costs" 
                  value={dashboardSummary.coverage.landed_cost.plants_missing_approved_landed_cost} 
                  sub={dashboardSummary.coverage.landed_cost.plants_missing_approved_landed_cost > 0 ? "Blocker" : null}
                />
              </div>

              {/* Card 5: Variable Costs */}
              <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: 6, padding: 12 }}>
                <div style={{ fontSize: 10, color: "var(--ink-dim)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>Variable Cost Coverage</div>
                
                <CoverageRow label="Available Agreements" value={dashboardSummary.coverage.variable_cost.available_record_count} />
                <CoverageRow label="Approved Agreements" value={dashboardSummary.coverage.variable_cost.approved_count} />
                <CoverageRow label="Pending Review" value={dashboardSummary.coverage.variable_cost.pending_review_count} />
                <CoverageRow label="Latest Date" value={dashboardSummary.coverage.variable_cost.latest_effective_date || "—"} />
              </div>
            </div>
          </div>

          {/* Section: Latest Optimization Card */}
          <div className="panel" style={{ padding: 18 }}>
            <div className="panel-header" style={{ marginBottom: 14 }}>
              <span className="panel-title">Latest Optimization Card</span>
              <span className="panel-badge violet">LIVE BACKEND DATA</span>
            </div>

            {!dashboardSummary.optimization.latest_run_exists ? (
              <div style={{ padding: "10px 0" }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)" }}>No optimization run available yet.</div>
                <div style={{ fontSize: 12, color: "var(--ink-muted)", marginTop: 4 }}>
                  System readiness is currently <span style={{ color: "var(--teal)", fontWeight: 700 }}>{dashboardSummary.metadata.system_status}</span>. Please execute the solver when all blockers are cleared.
                </div>
              </div>
            ) : dashboardSummary.optimization.run_status === "INCOMPLETE" ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "var(--coral)", display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: "var(--coral)" }} />
                    OPTIMIZATION RUN INCOMPLETE
                  </div>
                  <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-dim)" }}>
                    Time: {fmtTs(dashboardSummary.optimization.completed_at || dashboardSummary.optimization.created_at)}
                  </span>
                </div>

                {dashboardSummary.optimization.run_message && (
                  <div style={{
                    padding: 10,
                    borderRadius: 6,
                    background: "rgba(220,38,38,0.03)",
                    border: "1px dashed rgba(220,38,38,0.2)",
                    fontSize: 11,
                    fontFamily: "var(--font-mono)",
                    color: "var(--coral)",
                  }}>
                    {dashboardSummary.optimization.run_message}
                  </div>
                )}

                <div style={{
                  padding: 12,
                  borderRadius: 6,
                  background: "rgba(217,119,6,0.05)",
                  borderLeft: "4px solid var(--amber)",
                  fontSize: 12,
                  color: "var(--ink)",
                  fontWeight: 500,
                }}>
                  Resolve pending operational inputs before running optimization again.
                </div>
              </div>
            ) : (
              // COMPLETED Run
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "var(--teal)", display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: "var(--teal)", animation: "pulse-dot 2s ease infinite" }} />
                    SOLVER ALLOCATION SUCCESSFUL
                  </div>
                  <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-dim)" }}>
                    Completed At: {fmtTs(dashboardSummary.optimization.completed_at)}
                  </span>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 12 }}>
                  <div style={{ background: "rgba(255,255,255,0.01)", border: "1px dashed var(--border)", borderRadius: 6, padding: 10 }}>
                    <div style={{ fontSize: 9, color: "var(--ink-dim)", textTransform: "uppercase" }}>Plants Covered</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)", marginTop: 4 }}>
                      {dashboardSummary.optimization.plants_covered_count}
                    </div>
                  </div>

                  <div style={{ background: "rgba(255,255,255,0.01)", border: "1px dashed var(--border)", borderRadius: 6, padding: 10 }}>
                    <div style={{ fontSize: 9, color: "var(--ink-dim)", textTransform: "uppercase" }}>Total Demand</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)", marginTop: 4 }}>
                      {fmtQty(dashboardSummary.optimization.total_demand_mt)}
                    </div>
                  </div>

                  <div style={{ background: "rgba(255,255,255,0.01)", border: "1px dashed var(--border)", borderRadius: 6, padding: 10 }}>
                    <div style={{ fontSize: 9, color: "var(--ink-dim)", textTransform: "uppercase" }}>Total Allocated</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: "var(--teal)", marginTop: 4 }}>
                      {fmtQty(dashboardSummary.optimization.total_allocated_mt)}
                    </div>
                  </div>

                  <div style={{ background: "rgba(255,255,255,0.01)", border: "1px dashed var(--border)", borderRadius: 6, padding: 10 }}>
                    <div style={{ fontSize: 9, color: "var(--ink-dim)", textTransform: "uppercase" }}>Market Top-Up</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: dashboardSummary.optimization.market_top_up_mt > 0 ? "var(--coral)" : "var(--ink-dim)", marginTop: 4 }}>
                      {fmtQty(dashboardSummary.optimization.market_top_up_mt)}
                    </div>
                  </div>

                  <div style={{ background: "rgba(255,255,255,0.01)", border: "1px dashed var(--border)", borderRadius: 6, padding: 10 }}>
                    <div style={{ fontSize: 9, color: "var(--ink-dim)", textTransform: "uppercase" }}>Estimated Cost</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: "var(--amber)", marginTop: 4 }}>
                      {fmtCost(dashboardSummary.optimization.total_estimated_cost)}
                    </div>
                  </div>

                  <div style={{ background: "rgba(255,255,255,0.01)", border: "1px dashed var(--border)", borderRadius: 6, padding: 10 }}>
                    <div style={{ fontSize: 9, color: "var(--ink-dim)", textTransform: "uppercase" }}>Allocation Lines</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: "var(--violet)", marginTop: 4 }}>
                      {dashboardSummary.optimization.allocation_count}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Section: Recommended Next Actions */}
          <div className="panel" style={{ padding: 18 }}>
            <div className="panel-header" style={{ marginBottom: 14 }}>
              <span className="panel-title">Recommended Next Actions</span>
              <span className="panel-badge teal">LIVE BACKEND DATA</span>
            </div>

            {latestRecommendations && latestRecommendations.recommendations && latestRecommendations.recommendations.length > 0 ? (
              <div>
                {latestRecommendations.recommendations.map((rec) => (
                  <RecommendationCard key={rec.recommendation_key} rec={rec} />
                ))}
              </div>
            ) : (
              <div style={{
                textAlign: "center",
                padding: "24px 0",
                color: "var(--ink-dim)",
                fontSize: 13,
                fontFamily: "var(--font-mono)",
              }}>
                No operational actions are currently pending.
              </div>
            )}
          </div>
          
        </div>
      )}
    </div>
  );
}
