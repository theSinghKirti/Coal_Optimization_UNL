/**
 * BackendStatusPanel.jsx
 *
 * Compact sidebar panel showing live backend connectivity and key system
 * metrics.  All data is fetched independently from the existing demoSnapshot.json
 * pipeline — this panel does NOT replace demo data.
 *
 * Displayed fields:
 *  1. Backend Connected / Offline
 *  2. Validation Status  (overall_status)
 *  3. Total Issues       (total_issues count)
 *  4. Latest Optimization Status
 *  5. Latest Optimization Run Time
 *  6. Daily Stock Summary (plants with data / total active plants)
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { apiUrl } from "./api";

// How often to refresh backend status (ms)
const POLL_INTERVAL_MS = 30_000;

// ── Small helpers ────────────────────────────────────────────────────────────

function safeFetch(url) {
  return fetch(url, { headers: { Accept: "application/json" } })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
    .catch(() => null); // null signals "unavailable"
}

function Row({ label, value, valueColor, mono = false }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        minHeight: 20,
      }}
    >
      <span
        style={{
          fontSize: 10,
          color: "var(--ink-dim)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          fontFamily: "var(--font-body)",
          flexShrink: 0,
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: 11,
          fontWeight: 700,
          color: valueColor || "var(--ink)",
          fontFamily: mono ? "var(--font-mono)" : "var(--font-body)",
          textAlign: "right",
          maxWidth: "55%",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {value}
      </span>
    </div>
  );
}

// ── Status colour helpers ────────────────────────────────────────────────────

function connColor(connected) {
  return connected ? "var(--teal)" : "var(--coral)";
}

function validationColor(status) {
  if (!status) return "var(--ink-dim)";
  if (status === "READY") return "var(--teal)";
  if (status === "WARNING") return "var(--amber)";
  return "var(--coral)"; // INCOMPLETE
}

function optColor(status) {
  if (!status) return "var(--ink-dim)";
  const s = status.toUpperCase();
  if (s === "COMPLETED") return "var(--teal)";
  if (s === "FAILED") return "var(--coral)";
  return "var(--amber)";
}

function formatRunTime(ts) {
  if (!ts) return "—";
  try {
    const d = new Date(ts);
    if (isNaN(d)) return "—";
    return d.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return "—";
  }
}

// ── Main component ───────────────────────────────────────────────────────────

export default function BackendStatusPanel() {
  const [connected, setConnected] = useState(null); // null = initial probe
  const [validation, setValidation] = useState(null);
  const [optRun, setOptRun] = useState(null);
  const [stockSummary, setStockSummary] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  const timerRef = useRef(null);

  const refresh = useCallback(async () => {
    // 1. Health — determines connectivity
    const health = await safeFetch(apiUrl("/health"));
    setConnected(health !== null && health.status === "ok");

    if (health === null) {
      // Backend offline — clear stale data
      setValidation(null);
      setOptRun(null);
      setStockSummary(null);
      setLastRefresh(new Date());
      return;
    }

    // 2-4. Parallel fetches — each tolerates failure independently
    const [val, opt, stock] = await Promise.all([
      safeFetch(apiUrl("/validation/summary")),
      safeFetch(apiUrl("/optimization/latest")),
      safeFetch(apiUrl("/daily-stock/summary/latest")),
    ]);

    setValidation(val);
    setOptRun(opt);
    setStockSummary(Array.isArray(stock) ? stock : null);
    setLastRefresh(new Date());
  }, []);

  useEffect(() => {
    refresh();
    timerRef.current = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(timerRef.current);
  }, [refresh]);

  // ── Derived display values ───────────────────────────────────────────────

  const connLabel = connected === null ? "Probing…" : connected ? "Connected" : "Offline";
  const connCol = connected === null ? "var(--ink-dim)" : connColor(connected);

  const valStatus = validation?.overall_status ?? (connected === false ? "—" : "…");
  const valIssues =
    validation != null ? String(validation.total_issues) : connected === false ? "—" : "…";
  const valCol = validationColor(validation?.overall_status);

  const optStatus = optRun?.status ?? (connected === false ? "—" : "…");
  const optRunTime = optRun?.run_timestamp
    ? formatRunTime(optRun.run_timestamp)
    : connected === false
    ? "—"
    : "…";
  const optCol = optColor(optRun?.status);

  const stockText = (() => {
    if (!connected && connected !== null) return "—";
    if (!stockSummary) return connected === null ? "…" : "No data";
    const withData = stockSummary.filter((p) => p.report_date != null).length;
    return `${withData} / ${stockSummary.length} plants`;
  })();

  const refreshLabel = lastRefresh
    ? lastRefresh.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })
    : null;

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div
      id="backend-status-panel"
      style={{
        background: "var(--bg)",
        border: "1.5px solid var(--border)",
        borderRadius: 10,
        padding: "10px 12px",
        display: "flex",
        flexDirection: "column",
        gap: 7,
      }}
    >
      {/* Header row */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 2,
        }}
      >
        <span
          style={{
            fontSize: 9,
            fontFamily: "var(--font-mono)",
            fontWeight: 700,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--ink-muted)",
          }}
        >
          API Status
        </span>
        <button
          onClick={refresh}
          title="Refresh backend status"
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            fontSize: 11,
            color: "var(--ink-dim)",
            padding: "0 2px",
            lineHeight: 1,
          }}
        >
          ↻
        </button>
      </div>

      {/* Connectivity */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 7,
          paddingBottom: 6,
          borderBottom: "1px solid var(--border)",
          marginBottom: 1,
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: connCol,
            flexShrink: 0,
            animation: connected ? "pulse-dot 2s ease infinite" : "none",
            display: "inline-block",
          }}
        />
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: connCol,
            fontFamily: "var(--font-mono)",
            letterSpacing: "0.05em",
          }}
        >
          {connLabel}
        </span>
      </div>

      {/* Metric rows */}
      <Row label="Validation" value={valStatus} valueColor={valCol} mono />
      <Row
        label="Issues"
        value={valIssues}
        valueColor={
          validation?.total_issues > 0 ? "var(--coral)" : "var(--teal)"
        }
        mono
      />
      <Row label="Opt. Status" value={optStatus} valueColor={optCol} mono />
      <Row label="Last Run" value={optRunTime} mono />
      <Row label="Daily Stock" value={stockText} mono />

      {/* Last-refresh timestamp */}
      {refreshLabel && (
        <div
          style={{
            marginTop: 2,
            fontSize: 9,
            color: "var(--ink-dim)",
            fontFamily: "var(--font-mono)",
            textAlign: "right",
            borderTop: "1px solid var(--border)",
            paddingTop: 5,
          }}
        >
          refreshed {refreshLabel}
        </div>
      )}
    </div>
  );
}
