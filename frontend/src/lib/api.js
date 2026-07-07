/**
 * api.js — Shared API configuration for the CODSP frontend.
 *
 * Responsibilities:
 *  - Read VITE_API_BASE_URL from the Vite environment.
 *  - Normalize the base URL (strip trailing slash).
 *  - Expose a reusable `apiBase` constant for all fetch calls.
 *  - Provide a minimal `checkHealth()` helper for Phase 0 verification.
 *
 * Do NOT import this module inside the demo-data path;
 * existing components still fall back to demoSnapshot.json and
 * their own legacy API_BASE constants until Phase 1 wiring begins.
 */

/**
 * Normalized base URL that every API call should be prefixed with.
 * Reads VITE_API_BASE_URL from the Vite environment, falling back to
 * http://127.0.0.1:8001/api/v1 for local development.
 *
 * The env value should already include "/api/v1" (see .env.example).
 *
 * @type {string}
 */
export const apiBase = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001/api/v1"
).replace(/\/+$/, ""); // strip any trailing slash

/**
 * Build a full URL for a given API path segment.
 *
 * @param {string} path - e.g. "/daily-stock" or "/health"
 * @returns {string}
 *
 * @example
 * apiUrl("/health")   // "http://127.0.0.1:8001/api/v1/health"
 * apiUrl("/daily-stock/summary/latest")
 */
export function apiUrl(path) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${apiBase}${normalizedPath}`;
}

/**
 * checkHealth — calls GET /api/v1/health and returns the parsed JSON body.
 *
 * Used only for Phase 0 connectivity verification; not wired into the
 * dashboard UI yet.
 *
 * @returns {Promise<{ status: string, database: string }>}
 * @throws {Error} if the network request fails or the server returns non-2xx
 */
export async function checkHealth() {
  const response = await fetch(apiUrl("/health"), {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(
      `Health check failed: HTTP ${response.status} ${response.statusText}`
    );
  }
  return response.json();
}

/**
 * getDashboardSummary — calls GET /api/v1/dashboard/summary
 *
 * @returns {Promise<any>}
 */
export async function getDashboardSummary() {
  const response = await fetch(apiUrl("/dashboard/summary"), {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard summary: HTTP ${response.status}`);
  }
  return response.json();
}

/**
 * getLatestRecommendations — calls GET /api/v1/recommendations/latest
 *
 * @returns {Promise<any>}
 */
export async function getLatestRecommendations() {
  const response = await fetch(apiUrl("/recommendations/latest"), {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch recommendations: HTTP ${response.status}`);
  }
  return response.json();
}
