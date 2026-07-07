/**
 * LiveFuelPosition.jsx
 *
 * Read-only live daily stock panel for the Fuel Position tab.
 * Phase 1B — connects to:
 *   GET /api/v1/daily-stock/summary/latest   (stock_days, plant_name, report_date)
 *   GET /api/v1/daily-stock                  (full rows: opening, receipt, consumption, closing, recon)
 *
 * Field mapping from backend to display:
 *   DailyStockRead.opening_stock_mt   → Opening
 *   DailyStockRead.receipt_mt         → Receipt
 *   DailyStockRead.consumption_mt     → Consumption
 *   DailyStockRead.closing_stock_mt   → Closing
 *   DailyStockRead.reconciliation_difference_mt → Recon delta
 *   DailyStockRead.validation_status  → "ok" | "warning"
 *   LatestStockSummaryItem.stock_days  → Days of cover
 *   LatestStockSummaryItem.plant_name  → Plant name (human readable)
 *
 * States handled:
 *   - Backend offline     → BACKEND OFFLINE banner, no crash
 *   - No records in DB    → "No live daily stock records available."
 *   - Partial data        → shows what is available, marks missing as —
 *   - Data present        → LIVE BACKEND DATA table
 */

import React, { useMemo } from "react";

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmt(val, decimals = 0) {
  if (val == null || isNaN(val)) return "—";
  return Number(val).toLocaleString("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtMT(val) {
  if (val == null || isNaN(val)) return "—";
  const n = Number(val);
  if (n >= 1000) return (n / 1000).toFixed(1) + "k MT";
  return n.toFixed(0) + " MT";
}

// ── Sub-components ────────────────────────────────────────────────────────────

function DataBanner({ label, color }) {
  const styles = {
    LIVE: { bg: "rgba(13,148,136,0.08)", border: "rgba(13,148,136,0.30)", text: "var(--teal)" },
    DEMO: { bg: "rgba(124,58,237,0.08)", border: "rgba(124,58,237,0.25)", text: "var(--violet)" },
    "BACKEND OFFLINE": { bg: "rgba(220,38,38,0.07)", border: "rgba(220,38,38,0.25)", text: "var(--coral)" },
    "NO LIVE DATA": { bg: "rgba(148,163,184,0.10)", border: "rgba(148,163,184,0.30)", text: "var(--ink-dim)" },
  };
  const s = styles[label] || styles["NO LIVE DATA"];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "2px 8px",
        borderRadius: 20,
        background: s.bg,
        border: `1.5px solid ${s.border}`,
        color: s.text,
        fontSize: 9,
        fontWeight: 700,
        fontFamily: "var(--font-mono)",
        letterSpacing: "0.08em",
        textTransform: "uppercase",
      }}
    >
      {label === "LIVE" && (
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: s.text, display: "inline-block", animation: "pulse-dot 2s ease infinite" }} />
      )}
      {label}
    </span>
  );
}

function EmptyState({ message }) {
  return (
    <div
      style={{
        padding: "28px 0",
        textAlign: "center",
        color: "var(--ink-dim)",
        fontFamily: "var(--font-mono)",
        fontSize: 12,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
      }}
    >
      <span style={{ fontSize: 28 }}>📭</span>
      <span>{message}</span>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function LiveFuelPosition({ liveData }) {
  const { connected, stock, detailedStock, plants, loading, refresh, lastRefresh } = liveData;

  // Build UUID → plant name lookup map from plants master list
  const plantMap = useMemo(() => {
    if (!plants) return {};
    return Object.fromEntries(plants.map((p) => [p.id, p.plant_name]));
  }, [plants]);

  // Enrich the summary (stock[]) with full-detail rows (detailedStock[])
  // joined on plant_id. Summary gives stock_days; detail gives opening/receipt/consumption/recon.
  const enrichedRows = useMemo(() => {
    if (!stock) return null;

    // Index detailed rows by plant_id for O(1) lookup
    const detailByPlantId = {};
    if (detailedStock) {
      detailedStock.forEach((row) => {
        // Keep the most recent record per plant (service already returns latest per plant,
        // but guard just in case multiple dates appear)
        const existing = detailByPlantId[row.plant_id];
        if (!existing || row.report_date > existing.report_date) {
          detailByPlantId[row.plant_id] = row;
        }
      });
    }

    return stock.map((s) => {
      const detail = detailByPlantId[s.plant_id] ?? null;
      return {
        plant_id: s.plant_id,
        plant_name: s.plant_name || plantMap[s.plant_id] || s.plant_code || s.plant_id,
        plant_code: s.plant_code,
        report_date: s.report_date,
        // From summary endpoint
        closing_stock_mt: s.closing_stock_mt,
        consumption_mt: s.consumption_mt,
        stock_days: s.stock_days,
        validation_status: s.validation_status,
        // From detail endpoint (may be null if daily-stock endpoint returned nothing)
        opening_stock_mt: detail?.opening_stock_mt ?? null,
        receipt_mt: detail?.receipt_mt ?? null,
        reconciliation_difference_mt: detail?.reconciliation_difference_mt ?? null,
      };
    }).sort((a, b) => {
      // Sort: warnings first, then by plant name
      if (a.validation_status === "warning" && b.validation_status !== "warning") return -1;
      if (b.validation_status === "warning" && a.validation_status !== "warning") return 1;
      return (a.plant_name || "").localeCompare(b.plant_name || "");
    });
  }, [stock, detailedStock, plantMap]);

  const isOffline = connected === false;
  const isProbing = connected === null;
  const hasData = enrichedRows && enrichedRows.length > 0;

  const latestDate = enrichedRows
    ? enrichedRows.reduce((d, r) => (r.report_date && r.report_date > d ? r.report_date : d), "")
    : null;

  const refreshTs = lastRefresh
    ? lastRefresh.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })
    : null;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="panel" id="live-fuel-position" style={{ marginBottom: 20 }}>
      {/* Header */}
      <div className="panel-header">
        <span className="panel-title" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          Daily Stock — Live Backend Data
          <DataBanner label={isOffline ? "BACKEND OFFLINE" : isProbing ? "NO LIVE DATA" : hasData ? "LIVE" : "NO LIVE DATA"} />
        </span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {refreshTs && (
            <span style={{ fontSize: 9, color: "var(--ink-dim)", fontFamily: "var(--font-mono)" }}>
              {refreshTs}
            </span>
          )}
          <button
            id="btn-refresh-fuel-position"
            onClick={refresh}
            style={{
              background: "var(--bg)",
              border: "1.5px solid var(--border)",
              borderRadius: 8,
              padding: "4px 10px",
              cursor: "pointer",
              fontSize: 11,
              fontFamily: "var(--font-mono)",
              color: "var(--ink-muted)",
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Body */}
      {isOffline ? (
        <div style={{
          background: "rgba(220,38,38,0.05)", border: "1.5px solid rgba(220,38,38,0.18)",
          borderRadius: 8, padding: "12px 16px", display: "flex", alignItems: "center", gap: 10, margin: "4px 0 8px"
        }}>
          <span style={{ fontSize: 18 }}>⚠️</span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--coral)", fontFamily: "var(--font-mono)" }}>Backend Offline</div>
            <div style={{ fontSize: 11, color: "var(--ink-muted)", marginTop: 2 }}>
              Cannot load live stock data. Demo snapshot displayed below.
            </div>
          </div>
        </div>
      ) : loading && !hasData ? (
        <EmptyState message="Loading live daily stock data…" />
      ) : !hasData ? (
        <EmptyState message="No live daily stock records available. Submit a daily fuel entry to see data here." />
      ) : (
        <>
          {latestDate && (
            <div style={{ fontSize: 11, color: "var(--ink-muted)", fontFamily: "var(--font-mono)", marginBottom: 10 }}>
              Report date: <strong style={{ color: "var(--ink)" }}>{latestDate}</strong>
              <span style={{ marginLeft: 12, color: "var(--ink-dim)" }}>
                {enrichedRows.filter(r => r.report_date != null).length} of {enrichedRows.length} plants reporting
              </span>
            </div>
          )}

          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Plant</th>
                  <th>Report Date</th>
                  <th>Opening (MT)</th>
                  <th>Receipt (MT)</th>
                  <th>Consumption (MT)</th>
                  <th>Closing (MT)</th>
                  <th>Stock Cover</th>
                  <th>Recon Δ</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {enrichedRows.map((r) => {
                  const level =
                    r.stock_days == null ? "safe"
                    : r.stock_days < 5 ? "critical"
                    : r.stock_days < 10 ? "warning"
                    : "safe";
                  const reconOk = !r.reconciliation_difference_mt || Math.abs(r.reconciliation_difference_mt) <= 0.01;
                  return (
                    <tr key={r.plant_id}>
                      <td>
                        <span className="fuel-plant-badge">{r.plant_name}</span>
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-muted)" }}>
                        {r.report_date || "—"}
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>{fmtMT(r.opening_stock_mt)}</td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>{fmtMT(r.receipt_mt)}</td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>{fmtMT(r.consumption_mt)}</td>
                      <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>{fmtMT(r.closing_stock_mt)}</td>
                      <td>
                        {r.stock_days != null ? (
                          <span className="stock-cover">
                            <span className={`days ${level}`}>{r.stock_days.toFixed(1)}</span>
                            <span className="unit">d</span>
                          </span>
                        ) : (
                          <span style={{ color: "var(--ink-dim)", fontFamily: "var(--font-mono)" }}>—</span>
                        )}
                      </td>
                      <td>
                        {r.reconciliation_difference_mt != null ? (
                          <span className={reconOk ? "flag-ok" : "flag-bad"} style={{ fontSize: 11 }}>
                            {reconOk
                              ? "✓ OK"
                              : `⚠ Δ${Math.abs(r.reconciliation_difference_mt).toFixed(2)} MT`}
                          </span>
                        ) : (
                          <span style={{ color: "var(--ink-dim)", fontFamily: "var(--font-mono)" }}>—</span>
                        )}
                      </td>
                      <td>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            fontFamily: "var(--font-mono)",
                            color: r.validation_status === "warning" ? "var(--amber)" : "var(--teal)",
                          }}
                        >
                          {r.validation_status === "warning" ? "⚠ WARNING" : r.validation_status === "ok" ? "✓ OK" : "—"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
