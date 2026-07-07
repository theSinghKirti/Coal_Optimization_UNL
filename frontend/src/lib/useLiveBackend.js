/**
 * useLiveBackend.js
 *
 * Custom React hook that fetches all available Phase 1A read-only backend
 * endpoints and exposes a stable, unified live-data object.
 *
 * Endpoints used (GET only — all exist in backend):
 *   /api/v1/health
 *   /api/v1/validation/summary
 *   /api/v1/optimization/latest
 *   /api/v1/optimization/runs/{run_id}/allocations  (only when latest run exists)
 *   /api/v1/daily-stock/summary/latest
 *   /api/v1/daily-stock                              (Phase 1B: full row detail)
 *   /api/v1/plants                                   (Phase 1B: UUID→name map)
 *
 * Guarantees:
 *   - Never throws; all failures produce null values.
 *   - Does not touch demoSnapshot.json or any existing component state.
 *   - Auto-refreshes every POLL_INTERVAL_MS milliseconds.
 *
 * Exposed shape:
 *   {
 *     loading: bool,
 *     connected: bool | null,   // null = first probe not done yet
 *     health: { status, database } | null,
 *     validation: ValidationSummary | null,
 *     optimization: OptimizationRunDetail | null,
 *     allocations: AllocationResultRead[] | null,
 *     stock: LatestStockSummaryItem[] | null,
 *     detailedStock: DailyStockRead[] | null,  // Phase 1B: full rows
 *     plants: PlantRead[] | null,              // Phase 1B: master list
 *     lastRefresh: Date | null,
 *     refresh: () => void,
 *   }
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { apiUrl } from "./api";

const POLL_INTERVAL_MS = 30_000;

/** Fetch JSON safely; returns null on any error (network, CORS, non-2xx). */
async function safeFetch(url) {
  try {
    const r = await fetch(url, { headers: { Accept: "application/json" } });
    if (!r.ok) return null;
    return r.json();
  } catch {
    return null;
  }
}

export function useLiveBackend() {
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(null);
  const [health, setHealth] = useState(null);
  const [validation, setValidation] = useState(null);
  const [optimization, setOptimization] = useState(null);
  const [allocations, setAllocations] = useState(null);
  const [stock, setStock] = useState(null);
  const [detailedStock, setDetailedStock] = useState(null); // Phase 1B
  const [plants, setPlants] = useState(null);               // Phase 1B
  const [dashboardSummary, setDashboardSummary] = useState(null);
  const [latestRecommendations, setLatestRecommendations] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  const timerRef = useRef(null);

  const refresh = useCallback(async () => {
    setLoading(true);

    // ── Step 1: health probe ─────────────────────────────────────────────────
    const healthData = await safeFetch(apiUrl("/health"));
    const isConnected = healthData !== null && healthData.status === "ok";
    setHealth(healthData);
    setConnected(isConnected);

    if (!isConnected) {
      // Backend offline — clear all stale live data and stop here.
      setValidation(null);
      setOptimization(null);
      setAllocations(null);
      setStock(null);
      setDetailedStock(null);
      setPlants(null);
      setDashboardSummary(null);
      setLatestRecommendations(null);
      setLastRefresh(new Date());
      setLoading(false);
      return;
    }

    // ── Step 2: parallel fetch of independent endpoints ──────────────────────
    const [valData, optData, stockData, detailedStockData, plantsData, summaryData, recsData] = await Promise.all([
      safeFetch(apiUrl("/validation/summary")),
      safeFetch(apiUrl("/optimization/latest")),
      safeFetch(apiUrl("/daily-stock/summary/latest")),
      safeFetch(apiUrl("/daily-stock?page_size=100")),      // Phase 1B: full detail rows
      safeFetch(apiUrl("/plants?page_size=100")),           // Phase 1B: UUID→name map
      safeFetch(apiUrl("/dashboard/summary")),
      safeFetch(apiUrl("/recommendations/latest")),
    ]);

    setValidation(valData);
    setOptimization(optData);
    setStock(Array.isArray(stockData) ? stockData : null);
    // detailedStock comes from the paginated wrapper {items: [...], total: N}
    setDetailedStock(Array.isArray(detailedStockData?.items) ? detailedStockData.items : null);
    // plants also comes from paginated wrapper
    setPlants(Array.isArray(plantsData?.items) ? plantsData.items : null);
    setDashboardSummary(summaryData);
    setLatestRecommendations(recsData);

    // ── Step 3: allocations — only when a completed run exists ───────────────
    const runId = optData?.id ?? null;
    const runStatus = (optData?.status ?? "").toUpperCase();
    if (runId && runStatus === "COMPLETED") {
      const allocData = await safeFetch(
        apiUrl(`/optimization/runs/${runId}/allocations`)
      );
      setAllocations(Array.isArray(allocData) ? allocData : null);
    } else {
      setAllocations(null);
    }

    setLastRefresh(new Date());
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    timerRef.current = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(timerRef.current);
  }, [refresh]);

  return {
    loading,
    connected,
    health,
    validation,
    optimization,
    allocations,
    stock,
    detailedStock,
    plants,
    dashboardSummary,
    latestRecommendations,
    lastRefresh,
    refresh,
  };
}
