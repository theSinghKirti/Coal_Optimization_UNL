# CODSP — Frontend/Backend Integration Phase 1B Report
# Read-Only Fuel Position and Allocation Data

> **Scope:** Read-only live data in Fuel Position tab and Allocation tab only.
> No writes, no form wiring, no chart replacement of demo, no demo data removed.
> **Date:** 2026-07-06

---

## Files Changed

### Modified Files

| File | Change |
|---|---|
| `frontend/src/lib/useLiveBackend.js` | Added `detailedStock` + `plants` state; two new parallel fetches; both exposed in return value |
| `frontend/src/components/FuelPositionTab.jsx` | Added `liveData` prop; imports + renders `LiveFuelPosition` at top; DEMO DATA divider above existing charts |
| `frontend/src/components/AllocationTab.jsx` | Added `liveData` prop; imports + renders `LiveAllocation` at top; DEMO DATA divider above existing charts |
| `frontend/src/App.jsx` | Added `liveData={liveData}` prop to `<FuelPositionTab>` and `<AllocationTab>` renders |

### New Files Created

| File | Purpose |
|---|---|
| `frontend/src/components/LiveFuelPosition.jsx` | Live daily stock panel for Fuel Position tab |
| `frontend/src/components/LiveAllocation.jsx` | Live allocation panel for Allocation tab (all 4 states) |

### Unchanged Files

- `frontend/src/data/demoSnapshot.json` — untouched
- `frontend/src/lib/supabaseClient.js` — untouched
- All backend files — untouched

---

## Backend Endpoints Used

| Endpoint | Method | Purpose | Consumed by |
|---|---|---|---|
| `GET /api/v1/health` | GET | Connectivity probe | `useLiveBackend` (Step 1) |
| `GET /api/v1/daily-stock/summary/latest` | GET | Stock cover days, plant name/code, report date, validation status | `LiveFuelPosition` via hook |
| `GET /api/v1/daily-stock?page_size=100` | GET | Full detail rows: opening, receipt, consumption, closing, reconciliation delta | `LiveFuelPosition` via hook |
| `GET /api/v1/plants?page_size=100` | GET | UUID → plant_name resolution map | Both live components via hook |
| `GET /api/v1/optimization/latest` | GET | Run status, run_timestamp, total_estimated_cost, notes, stored validation_summary | `LiveAllocation` via hook |
| `GET /api/v1/optimization/runs/{run_id}/allocations` | GET | Allocation rows (only when status = COMPLETED) | `LiveAllocation` via hook |

No endpoints were invented. All 6 endpoints verified to exist in the backend router files.

---

## Live Fields Shown — Fuel Position Tab

Panel title: **Daily Stock — Live Backend Data**

| Field | Source | Notes |
|---|---|---|
| Plant name | `LatestStockSummaryItem.plant_name` or `plants` map by `plant_id` | Human-readable, not UUID |
| Report date | `LatestStockSummaryItem.report_date` | Per-plant latest date |
| Opening stock | `DailyStockRead.opening_stock_mt` | From detailed stock endpoint |
| Receipt | `DailyStockRead.receipt_mt` | From detailed stock endpoint |
| Consumption | `DailyStockRead.consumption_mt` | From both endpoints |
| Closing stock | `LatestStockSummaryItem.closing_stock_mt` | From summary endpoint |
| Stock cover days | `LatestStockSummaryItem.stock_days` | Only shown if backend provides it — no fabricated values |
| Reconciliation delta | `DailyStockRead.reconciliation_difference_mt` | ✓ OK or ⚠ Δ{x} MT |
| Validation status | `DailyStockRead.validation_status` | "ok" → ✓ OK, "warning" → ⚠ WARNING |
| Plants reporting count | computed: `stock.filter(p => p.report_date != null).length` | "X of Y plants reporting" |

Rows are sorted: warnings first, then alphabetical by plant name.

---

## Live Fields Shown — Allocation Tab

Panel title: **Allocation — Live Backend Data**

### State A — COMPLETED run

| Field | Source |
|---|---|
| Run timestamp | `OptimizationRunDetail.run_timestamp` |
| Total estimated cost | `OptimizationRunDetail.total_estimated_cost` |
| Allocation line count | `allocations.length` |
| Market top-up required | `allocations.some(a => a.allocation_type === "market_topup")` |
| Plant name | `plants` UUID map from `AllocationResultRead.plant_id` |
| Allocation type | `AllocationResultRead.allocation_type` → FSA / Bridge / Market labels |
| Quantity | `AllocationResultRead.quantity_mt` |
| Unit cost | `AllocationResultRead.unit_cost` |
| Estimated cost | `AllocationResultRead.estimated_cost` |
| ACQ utilisation | `AllocationResultRead.acq_utilization_pct` (bar + % label) |

> Note: `AllocationResultRead` does not carry a company name field — allocation type (FSA/Bridge/Market) is used as the source label, which accurately reflects the contract type.

### State B — INCOMPLETE run

- Shows OPTIMIZATION INCOMPLETE badge
- Displays run timestamp
- Shows stored `optimization.validation_summary.issues` (up to 5 blocking reasons with severity labels)
- Shows `optimization.notes` if present
- Shows guidance: "Complete or approve required operational inputs before running optimization."
- **No demo allocations shown as live**

### State C — No run yet

- Shows "No optimization run available yet." empty state
- Guidance on how to trigger one

### State D — FAILED run

- Shows FAILED status with run timestamp
- Shows "The last optimization run encountered an error" message
- Shows stored reasons if available

---

## Offline / Fallback Behaviour

| Scenario | Fuel Position Tab | Allocation Tab |
|---|---|---|
| Backend offline | BACKEND OFFLINE banner inside live panel; DEMO DATA divider; demo charts render normally below | BACKEND OFFLINE banner inside live panel; DEMO DATA divider; demo charts render normally below |
| Initial probe (null) | "Connecting to backend…" shown in live panel | "Connecting to backend…" shown |
| No stock records in DB | "No live daily stock records available. Submit a daily fuel entry to see data here." | n/a |
| `detailedStock` endpoint fails | Opening/Receipt/Recon columns show "—"; summary data (closing, stock days) still shown | n/a |
| `plants` endpoint fails | Plant name falls back to `plant_code` then raw UUID | Plant name falls back to raw UUID |
| `allocations` endpoint fails | n/a | Allocation table shows "No allocation rows returned" |
| App crash | **Never** — all safeFetch calls catch all errors and return null; all render paths guard on null | Same guarantee |

The existing demo charts and tables **always render** below the DEMO DATA divider, regardless of backend state.

---

## Data Label Guarantee

Every live section carries exactly one of these visible labels:

| Label | When shown |
|---|---|
| `LIVE` (pulsing dot, teal) | Backend connected, data present |
| `BACKEND OFFLINE` (coral) | Health check failed |
| `NO LIVE DATA` (muted) | Connected but no records |
| `OPTIMIZATION INCOMPLETE` (coral) | Run status is INCOMPLETE or FAILED |
| `DEMO DATA` (violet) | Fixed divider above all existing demo content |

Demo figures and live backend figures are **never mixed in the same table or chart**.

---

## Hook Architecture — useLiveBackend (updated)

```
refresh() {
  Step 1: safeFetch(/health)
    → offline: clear all state, return

  Step 2: Promise.all([
    /validation/summary,
    /optimization/latest,
    /daily-stock/summary/latest,
    /daily-stock?page_size=100,        ← NEW Phase 1B
    /plants?page_size=100,             ← NEW Phase 1B
  ])
  → setStock(summary items)
  → setDetailedStock(items from paginated wrapper)
  → setPlants(items from paginated wrapper)

  Step 3: if optimization.status === COMPLETED:
    safeFetch(/optimization/runs/{id}/allocations)
}
Auto-polls every 30 seconds.
```

---

## Local Run Commands

```powershell
# Backend (port 8001)
cd C:\Users\itisa\Desktop\mdsir
.venv\Scripts\Activate.ps1
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

# Frontend (port 5173)
cd C:\Users\itisa\Desktop\mdsir\frontend
Copy-Item .env.example .env   # first time only
npm run dev
```

Open http://localhost:5173 → **Fuel Position** tab → live panel at top, demo divider below.
Open http://localhost:5173 → **Allocation** tab → live panel at top (state depends on whether an optimization run exists), demo divider below.

---

## Verification Results

| Check | Result |
|---|---|
| `npm run build` | ✅ 847 modules, built in 4.10s |
| `ruff check backend/` | ✅ All checks passed |
| `pytest backend/tests/` | ✅ 45 passed |
| No new npm packages installed | ✅ |
| No backend code modified | ✅ |
| `demoSnapshot.json` untouched | ✅ |
| Supabase code untouched | ✅ |
| All 9 existing tabs preserved | ✅ |
| Demo content labelled DEMO DATA | ✅ |
| Live content labelled LIVE / NO LIVE DATA / BACKEND OFFLINE | ✅ |

---

## What Is NOT Done (Deferred to Phase 2+)

- [ ] Wire `DailyFuelForm` POST to `/api/v1/daily-stock`
- [ ] Wire document upload to `/api/v1/documents/upload`
- [ ] Wire review/approve/reject actions
- [ ] Replace demo KPI cards with live optimization values
- [ ] Replace demo allocation charts with live chart data
- [ ] ACQ Registry tab live wiring
- [ ] Plant Status tab live wiring
- [ ] Audit Log tab live wiring
