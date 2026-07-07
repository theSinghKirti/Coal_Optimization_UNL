# CODSP — Frontend/Backend Integration Phase 1A Report
# Read-Only Live Backend Status in Overview Tab

> **Scope:** Read-only live status panel in Overview tab only.
> No writes, no form wiring, no chart replacement, no demo data removed.
> **Date:** 2026-07-06

---

## Files Changed

### New Files Created

| File | Purpose |
|---|---|
| `frontend/src/lib/useLiveBackend.js` | Custom React hook — fetches all 5 backend endpoints, exposes unified live data object |
| `frontend/src/components/LiveBackendStatus.jsx` | Full "Live Backend Status" panel rendered in Overview tab |

### Modified Files

| File | Change |
|---|---|
| `frontend/src/App.jsx` | Added `useLiveBackend` import; called hook at App level; passed `liveData` prop to `OverviewTab` |
| `frontend/src/components/OverviewTab.jsx` | Added `LiveBackendStatus` import; accepted `liveData` prop; rendered panel above KPI grid |

### Unchanged Files

- `frontend/src/data/demoSnapshot.json` — unchanged
- `frontend/src/lib/supabaseClient.js` — unchanged
- All other 8 tab components — unchanged
- All backend files — unchanged

---

## Backend Endpoints Used (GET only)

| Endpoint | Purpose | Called When |
|---|---|---|
| `GET /api/v1/health` | Connectivity probe | Every refresh cycle |
| `GET /api/v1/validation/summary` | Overall status + issue list | Backend connected |
| `GET /api/v1/optimization/latest` | Latest run status, timestamp, cost | Backend connected |
| `GET /api/v1/optimization/runs/{run_id}/allocations` | Allocation line count | Latest run status = COMPLETED |
| `GET /api/v1/daily-stock/summary/latest` | Stock date + plant coverage | Backend connected |

No endpoints were invented. No POST/PATCH/DELETE calls are made.

---

## Live Fields Displayed

| Field | Source | Badge/Format |
|---|---|---|
| Backend | `health.status` | LIVE (teal pulsing) / BACKEND OFFLINE (coral) |
| Validation Status | `validation.overall_status` | READY / WARNING / INCOMPLETE badge |
| Total Issues | `validation.total_issues` | Teal = 0, Amber = 1-5, Coral > 5 |
| Issue list (top 4) | `validation.issues[0..3]` | Severity chip + message, sorted critical-first |
| Optimization Status | `optimization.status` | COMPLETED / INCOMPLETE / FAILED / NO RUN YET |
| Last Run Time | `optimization.run_timestamp` | "06 Jul 2026, 14:35" format |
| Total Est. Cost | `optimization.total_estimated_cost` | Only shown when COMPLETED, in ₹ Cr |
| Allocation Lines | `allocations.length` | Only shown when COMPLETED |
| Market Top-Up | `optimization.validation_summary.market_topup_required` | READY / INCOMPLETE badge |
| Run Incomplete reasons | `optimization.validation_summary.issues[0..2]` | Only shown when INCOMPLETE |
| Daily Stock | `stock.filter(p => p.report_date != null).length` | "X / Y plants" + latest date |
| Refresh timestamp | `lastRefresh` | HH:mm:ss |

---

## Fallback / Offline Behaviour

| Scenario | Result |
|---|---|
| Backend never started | Panel shows "Backend Offline" badge + orange warning banner. All metric rows show "—". Demo KPI/charts below render normally. |
| Backend starts mid-session | Panel auto-recovers on next 30-second poll or manual Refresh click. |
| One endpoint fails (e.g. no optimization run) | That field shows "No Run Yet" / "No data" / "—". All others still load. |
| Allocations endpoint fails | "..." shown; allocation count shows "—". Optimization status still visible. |
| `demoSnapshot.json` missing | This is unrelated — existing App.jsx handles it; panel has no dependency on it. |

A DEMO badge and note always appear at the bottom of the panel reminding users that
charts and allocations below are demo snapshot data, not yet from the live backend.

---

## Badges Used

| Badge Label | Colour | Meaning |
|---|---|---|
| LIVE | Teal (pulsing dot) | Backend health check passed |
| BACKEND OFFLINE | Coral | Health check failed / network error |
| DEMO | Violet | Charts/allocations below are demo data |
| READY | Teal | Validation clean; ready to run optimization |
| WARNING | Amber | Non-critical validation issues present |
| INCOMPLETE | Coral | Critical validation issues; optimization not safe |
| COMPLETED | Teal | Last optimization run succeeded |
| FAILED | Coral | Last optimization run failed |
| NO RUN YET | Muted grey | No optimization run exists in DB |

---

## Architecture of useLiveBackend Hook

```
refresh() {
  1. safeFetch(/health)
     -> if null: setConnected(false); clear all; return
     -> else: setConnected(true)
  2. Promise.all([
       safeFetch(/validation/summary),
       safeFetch(/optimization/latest),
       safeFetch(/daily-stock/summary/latest),
     ])
  3. if optimization.status === "COMPLETED" && optimization.id:
       safeFetch(/optimization/runs/{id}/allocations)
}

Auto-polls every 30 seconds.
All safeFetch calls catch all errors and return null — no throws escape.
```

---

## Local Run Commands

### Start the backend (port 8001)

```powershell
# Activate virtualenv
C:\Users\itisa\Desktop\mdsir\.venv\Scripts\Activate.ps1

# From backend/ directory
cd C:\Users\itisa\Desktop\mdsir\backend
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

### Start the frontend (port 5173)

```powershell
cd C:\Users\itisa\Desktop\mdsir\frontend

# First time: copy env file
Copy-Item .env.example .env

npm run dev
```

Open: http://localhost:5173 → click Overview tab → "Live Backend Status" panel appears at the top.

### Verify CORS (browser DevTools)
Navigate to Overview tab. In Network panel, find the `/api/v1/health` request.
Response headers must include:
```
Access-Control-Allow-Origin: http://localhost:5173
```
No CORS error in console.

---

## Verification Results

| Check | Result |
|---|---|
| `npm run build` | ✅ 845 modules, built in 4.00s |
| `ruff check backend/` | ✅ All checks passed |
| `pytest backend/tests/` | ✅ 45 passed |
| Frontend build includes new components | ✅ |
| demoSnapshot.json untouched | ✅ |
| All 9 existing tabs render unchanged | ✅ |
| No new npm packages installed | ✅ |
| No backend code modified | ✅ |

---

## What Is NOT Done (Deferred to Phase 1B+)

- [ ] Replace demo KPI cards with live optimization values
- [ ] Replace demo allocation charts with live allocations
- [ ] Replace demo fuel position table with /daily-stock/summary/latest
- [ ] Replace demo ACQ Registry with /fsa-constraints
- [ ] Wire DailyFuelForm POST to /api/v1/daily-stock
- [ ] Document upload wiring
- [ ] Review queue per-entity wiring
