# CODSP Frontend–Backend Integration Plan

> **Audit Only** — No code has been modified.
> Generated: 2026-07-06
> Workspace root: `c:\Users\itisa\Desktop\mdsir\`

---

## 1. Current Frontend Data Sources (Must Be Removed / Replaced)

### 1.1 `src/data/demoSnapshot.json`

| Consuming File | How Used | Remove / Replace |
|---|---|---|
| `src/App.jsx` (line 2) | Static import as `snapshot`; used as initial `snapshotData` state | Replace with live call to `GET /api/v1/dashboard/summary` |
| `src/App.jsx` (line 38) | `setSnapshotData(snapshot)` as React state default | Replace default with null / loading state |

The JSON blob has three top-level keys: `optimization`, `daily_fuel`, `constraints`. Each must map to a dedicated API call once the backend is connected.

### 1.2 `VITE_API_URL` fallback to `http://localhost:8000` (old base, no `/api/v1` prefix)

Every file that makes fetch calls uses:

```js
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
```

but then appends **legacy paths** like `/api/data/snapshot`, `/api/records/daily-fuel`, `/api/documents/review-queue` — none of which exist on the new backend. All paths must be rewritten to use the `/api/v1/` prefix.

**Files affected:**

| File | Lines Using API_BASE |
|---|---|
| `src/App.jsx` | 33, 44, 188 |
| `src/components/DailyFuelForm.jsx` | 6, 48 |
| `src/components/IppAgreementForm.jsx` | 73, 95, 132 |
| `src/components/DocumentCenterTab.jsx` | 26, 45, 73, 118 |
| `src/components/ReviewQueueTab.jsx` | 3, 14, 48 |
| `src/components/AuditLogTab.jsx` | 3, 11 |

### 1.3 `src/lib/supabaseClient.js`

Currently dormant — `supabase` is exported but searched nowhere in any component; it exports `null` because no env vars are set. Do NOT remove yet.

### 1.4 `mongodb` npm package

Listed in `package.json` but not imported anywhere. Zero usage. Safe to remove at any point.

### 1.5 Hard-coded mock array in `src/lib/utils.jsx`

```js
export const currentAllocations = [ /* 14 rows of historical baseline */ ];
```

Used by `App.jsx`, `OverviewTab.jsx`, `AllocationTab.jsx`, `PlantStatusTab.jsx` for **Baseline Cost** KPI. Must eventually be replaced by `GET /api/v1/landed-costs/latest` + `GET /api/v1/fsa-constraints`.

### 1.6 Hard-coded mock array in `src/components/IppAgreementForm.jsx`

```js
const INITIAL_AGREEMENTS = [ /* 5 hard-coded IPP agreements */ ];
```

Fallback when old endpoint `/api/records/ipp-agreements` fails. No equivalent backend endpoint exists.

---

## 2. Frontend File → Backend API Mapping

All backend routes are prefixed with `/api/v1` (from `settings.api_v1_prefix`).
Backend runs on `http://localhost:8000` by default.

### 2.1 App.jsx — Global Snapshot & Optimization Trigger

| Frontend Fetch | Current (Legacy) Path | Correct Backend Path | Method | Status |
|---|---|---|---|---|
| `fetchSnapshot()` | `/api/data/snapshot` | `/api/v1/dashboard/summary` | GET | PATH MISMATCH |
| Solve LP button | `/api/optimization/run` | `/api/v1/optimization/run` | GET -> POST | METHOD + PREFIX MISMATCH |

**Note:** `DashboardSummary` schema does NOT replicate the full `demoSnapshot.json` structure. The frontend must call multiple separate endpoints for `optimization`, `daily_fuel`, and `constraints`.

### 2.2 Health Check (not yet called by frontend)

| Correct Backend Path | Method |
|---|---|
| `/api/v1/health` | GET |

### 2.3 DailyFuelForm.jsx — Daily Stock Entry

| Frontend Fetch | Current (Legacy) Path | Correct Backend Path | Method |
|---|---|---|---|
| Submit daily fuel entry | `POST /api/records/daily-fuel` | `POST /api/v1/daily-stock` | POST |

**Payload field name differences:**

| Frontend sends | Backend expects (DailyStockCreate) |
|---|---|
| `plant` (name string) | `plant_id` (UUID) |
| `opening_balance` | `opening_stock_mt` |
| `receipt` | `receipt_mt` |
| `consumption_release` | `consumption_mt` |
| `closing_balance` | `closing_stock_mt` |
| `reconciliation_flag` | `validation_status` ("ok"/"warning") |
| `reconciliation_delta` | Derived server-side (no direct field) |

`plant_id` is a UUID from master data. Form must resolve it via `GET /api/v1/plants`.

### 2.4 FuelPositionTab.jsx — Display Daily Stock

| Frontend Fetch | Current Path | Correct Backend Path | Method |
|---|---|---|---|
| Load `daily_fuel` array | From `demoSnapshot.json` | `GET /api/v1/daily-stock/summary/latest` | GET |

Response is a list of `LatestStockSummaryItem`. Field mapping must be verified against component expectations.

### 2.5 RegistryTab.jsx — FSA / Bridge Constraint Registry

| Frontend Fetch | Current Path | Correct Backend Path | Method |
|---|---|---|---|
| Load `constraints` array | From `demoSnapshot.json` | `GET /api/v1/fsa-constraints` | GET |

Backend returns `plant_id` (UUID) and `company_id`. Frontend needs plant name join via `GET /api/v1/plants`.

### 2.6 AllocationTab / OverviewTab / PlantStatusTab — Optimization Results

| Frontend Fetch | Current Path | Correct Backend Path | Method |
|---|---|---|---|
| Load `optimization` object | From `demoSnapshot.json` | `GET /api/v1/optimization/latest` | GET |
| Get allocations for run | — | `GET /api/v1/optimization/runs/{run_id}/allocations` | GET |

demoSnapshot.json optimization shape (for reference):
```json
{
  "status": "Optimal",
  "plants_covered": [...],
  "allocations": [{ "plant", "company", "allocated_mt", "landed_cost_rs_mt", "acq_cap_mt", "acq_utilisation_pct" }],
  "shortfalls": [{ "plant", "shortfall_mt", "assumed_market_rate_rs_mt" }]
}
```
Verify field equivalence against `OptimizationRunDetail` / `AllocationResultRead`.

### 2.7 DocumentCenterTab.jsx — Document Upload & Registry

| Frontend Fetch | Current (Legacy) Path | Correct Backend Path | Method | Notes |
|---|---|---|---|---|
| List documents | `GET /api/documents` | `GET /api/v1/documents` | GET | Paginated — unwrap `.items` |
| Upload document | `POST /api/documents/upload` | `POST /api/v1/documents` | POST | Field mismatch — see below |
| Sync UPSLDC scraper | `POST /api/documents/sync-upsldc` | NO EQUIVALENT | — | NOT IMPLEMENTED |

**Upload FormData field differences:**

| Frontend sends | Backend expects |
|---|---|
| `file` | `file` OK |
| `doc_type` | `document_type` (renamed) |
| `plant_name` (string) | `plant_id` (UUID, optional) |
| `counterparty` | Not in backend schema |
| `period_start` | Not in backend schema |
| `period_end` | Not in backend schema |

Backend also exposes:
- `POST /api/v1/variable-cost/upload` — specialized VC PDF upload
- `POST /api/v1/documents/{document_id}/extract` — explicit extraction (FSA/LC types only)

### 2.8 ReviewQueueTab.jsx — Review & Approval Actions

| Frontend Fetch | Current (Legacy) Path | Correct Backend Path | Method | Notes |
|---|---|---|---|---|
| Fetch review queue | `GET /api/documents/review-queue` | NO EQUIVALENT | — | NOT IMPLEMENTED |
| Approve/Reject task | `POST /api/documents/review-queue/{taskId}/resolve` | Per-entity endpoints | — | Partial |

**Per-entity review endpoints (available but not unified):**

| Entity | Backend Endpoint | Method |
|---|---|---|
| FSA Constraint | `POST /api/v1/fsa-constraints/{record_id}/review` | POST JSON |
| Landed Cost | `POST /api/v1/landed-costs/{record_id}/review` | POST JSON |
| Variable Cost | `PATCH /api/v1/variable-cost/{vc_id}/review` | PATCH JSON |

### 2.9 AuditLogTab.jsx — Audit Trail

| Frontend Fetch | Current (Legacy) Path | Correct Backend Path | Method |
|---|---|---|---|
| Fetch audit logs | `GET /api/records/audit-logs` | `GET /api/v1/audit-logs` | GET |

Response is paginated (`Page[AuditLogRead]`); frontend expects plain array — must unwrap `.items`.

### 2.10 IppAgreementForm.jsx — IPP VC Agreements

| Frontend Fetch | Current (Legacy) Path | Correct Backend Path | Method |
|---|---|---|---|
| Load agreements | `GET /api/records/ipp-agreements` | NOT IMPLEMENTED | — |
| Save agreement | `POST /api/records/ipp-agreements` | NOT IMPLEMENTED | — |

---

## 3. Required Environment Variable

Create `frontend/.env`:

```env
# Base URL for the CODSP FastAPI backend — include /api/v1 prefix
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

> **Note:** Frontend currently reads `VITE_API_URL` (no `/api/v1`). When doing the remap, standardize on `VITE_API_BASE_URL` with the prefix included, so callers only append route paths like `/daily-stock`.

All 6 files using `API_BASE` must be updated to use the new env variable name.

---

## 4. Required Backend CORS Origins

**The backend has NO CORS middleware configured** (confirmed: grep for `CORS` in `app/` returns zero results).

When the Vite dev server (port 5173) calls the backend (port 8000), the browser will block ALL requests due to CORS policy.

The following CORS origins must be permitted in the backend:

```python
allowed_origins = [
    "http://localhost:5173",    # Vite dev server default
    "http://localhost:4173",    # Vite preview
    "http://127.0.0.1:5173",   # Alternative local
]
```

For production: add the actual deployment domain.
Middleware: `CORSMiddleware` from `starlette.middleware.cors`, to be added to `backend/app/main.py`.

---

## 5. Frontend Features That Can Connect Immediately

| Feature | Frontend File | Backend Endpoint | Blocker to Resolve |
|---|---|---|---|
| Health / Liveness | (none yet) | `GET /api/v1/health` | None — endpoint ready |
| Daily Stock Submit | `DailyFuelForm.jsx` | `POST /api/v1/daily-stock` | Payload field renaming + plant UUID lookup |
| Daily Stock View | `FuelPositionTab.jsx` | `GET /api/v1/daily-stock/summary/latest` | Field name mapping |
| Audit Log View | `AuditLogTab.jsx` | `GET /api/v1/audit-logs` | Pagination unwrap (.items) |
| Document Upload (basic) | `DocumentCenterTab.jsx` | `POST /api/v1/documents` | FormData field renaming + plant_id |
| Variable Cost Upload | `DocumentCenterTab.jsx` | `POST /api/v1/variable-cost/upload` | New upload path for VC type |
| Document List | `DocumentCenterTab.jsx` | `GET /api/v1/documents` | Pagination unwrap |
| Optimization Trigger | `App.jsx` topbar button | `POST /api/v1/optimization/run` | Change GET to POST; prefix fix |
| Optimization Latest Result | `AllocationTab`, `OverviewTab` | `GET /api/v1/optimization/latest` | Schema mapping + shortfall handling |
| FSA Constraint View | `RegistryTab.jsx` | `GET /api/v1/fsa-constraints` | Plant name join; pagination unwrap |
| Plant Master Data | All form dropdowns | `GET /api/v1/plants` | New call needed for UUID resolution |

---

## 6. Frontend Features That Must Remain Demo/Disabled

| Feature | Frontend File | Missing Endpoint | Reason |
|---|---|---|---|
| UPSLDC Scraper Sync | `DocumentCenterTab.jsx` | `POST /api/v1/documents/sync-upsldc` | Not implemented in backend |
| Unified Review Queue | `ReviewQueueTab.jsx` | `GET /api/v1/documents/review-queue` | No unified queue endpoint |
| Unified Approve/Reject | `ReviewQueueTab.jsx` | `POST /api/v1/documents/review-queue/{id}/resolve` | Per-entity endpoints only |
| IPP VC Agreement List | `IppAgreementForm.jsx` | `GET /api/v1/ipp-agreements` | Module does not exist |
| IPP VC Agreement Submit | `IppAgreementForm.jsx` | `POST /api/v1/ipp-agreements` | Module does not exist |
| Document counterparty/period | `DocumentCenterTab.jsx` upload form | N/A | Fields not in backend schema |

---

## 7. Safe Phased Implementation Order

### Phase 0 — Backend Prerequisites (Before Any Phase 1 Work)

1. Add `CORSMiddleware` to `backend/app/main.py` — allow `http://localhost:5173`
2. Create `frontend/.env` with `VITE_API_BASE_URL=http://localhost:8000/api/v1`
3. Seed plant master data — plants must exist in DB before any form resolves plant names to UUIDs

---

### Phase 1 — Read-Only Display Wiring (Lowest Risk)

Replace `demoSnapshot.json` reads with live data. No form submissions yet.

| Order | Action | Frontend File | Backend Call |
|---|---|---|---|
| 1a | Fetch audit logs from API | `AuditLogTab.jsx` | `GET /api/v1/audit-logs` (unwrap .items) |
| 1b | Fetch optimization latest result | `App.jsx`, `AllocationTab`, `OverviewTab`, `PlantStatusTab` | `GET /api/v1/optimization/latest` + `/runs/{id}/allocations` |
| 1c | Fetch FSA constraints | `RegistryTab.jsx` | `GET /api/v1/fsa-constraints` (resolve plant names from master data) |
| 1d | Fetch daily stock summary | `FuelPositionTab.jsx` | `GET /api/v1/daily-stock/summary/latest` |
| 1e | Fetch document list | `DocumentCenterTab.jsx` | `GET /api/v1/documents` (unwrap .items) |

---

### Phase 2 — Form Submission Wiring (Medium Risk)

| Order | Action | Frontend File | Backend Call |
|---|---|---|---|
| 2a | Wire plant dropdown from API | All forms | `GET /api/v1/plants` — cache for UUID resolution |
| 2b | Daily fuel/stock submission | `DailyFuelForm.jsx` | `POST /api/v1/daily-stock` (rename payload fields) |
| 2c | Document upload | `DocumentCenterTab.jsx` | `POST /api/v1/documents` (rename FormData fields) |
| 2d | Variable Cost PDF upload | `DocumentCenterTab.jsx` | `POST /api/v1/variable-cost/upload` |
| 2e | Optimization trigger | `App.jsx` topbar button | `POST /api/v1/optimization/run` (change method + prefix) |

---

### Phase 3 — Review & Approval Wiring (High Complexity)

| Order | Action | Notes |
|---|---|---|
| 3a | Option A: Build backend aggregate review-queue endpoint | Recommended — single GET returning all pending items across FSAConstraint, LandedCost, VariableCost |
| 3b | Option B: Rewrite ReviewQueueTab to call per-entity endpoints | Requires routing approve/reject to correct endpoint by item type |
| 3c | Wire per-entity review | `POST /api/v1/fsa-constraints/{id}/review`, `POST /api/v1/landed-costs/{id}/review`, `PATCH /api/v1/variable-cost/{id}/review` |

---

### Phase 4 — New Backend Features (Requires Backend Development)

| Feature | Backend Work Required |
|---|---|
| UPSLDC Scraper Sync | Implement `POST /api/v1/documents/sync-upsldc` endpoint |
| IPP VC Agreements | New module: model, schema, router, service for `ipp_agreements` table |
| Unified Review Queue | Add `GET /api/v1/review-queue` aggregate across all pending entity types |

---

### Phase 5 — Cleanup (After Phase 3 Complete)

| Action | Files Affected |
|---|---|
| Remove `demoSnapshot.json` import from App.jsx | `src/App.jsx` line 2 |
| Delete `src/data/demoSnapshot.json` | `src/data/` |
| Remove `currentAllocations` hard-coded array | `src/lib/utils.jsx` lines 72-88 |
| Remove `INITIAL_AGREEMENTS` hard-coded array | `IppAgreementForm.jsx` lines 15-71 |
| Remove `mongodb` from package.json | `package.json` |
| Evaluate Supabase removal | `src/lib/supabaseClient.js`, `package.json` |

---

## Appendix A — Complete Backend Route Reference

All routes have base prefix `/api/v1`:

| Module | Method | Path | Description |
|---|---|---|---|
| Health | GET | `/health` | API + DB liveness |
| Master Data | POST | `/plants` | Create plant |
| | GET | `/plants` | List plants (paginated) |
| | GET | `/plants/{plant_id}` | Get single plant |
| | PATCH | `/plants/{plant_id}` | Update plant |
| | POST | `/plants/aliases` | Create alias |
| | GET | `/plants/aliases` | List aliases |
| | POST | `/coal-companies` | Create coal company |
| | GET | `/coal-companies` | List coal companies |
| | POST | `/suppliers` | Create supplier |
| | GET | `/suppliers` | List suppliers |
| Daily Stock | POST | `/daily-stock` | Create daily stock record |
| | GET | `/daily-stock` | List records (paginated, filterable) |
| | GET | `/daily-stock/summary/latest` | Latest record per active plant |
| | GET | `/daily-stock/{record_id}` | Get single record |
| | PATCH | `/daily-stock/{record_id}` | Update record |
| Documents & VC | POST | `/documents` | Upload document |
| | GET | `/documents` | List documents (paginated) |
| | GET | `/documents/{document_id}` | Get single document |
| | POST | `/documents/{document_id}/extract` | Run FSA/LC extraction |
| | GET | `/documents/{document_id}/extraction` | Get extraction status |
| | POST | `/variable-cost/upload` | Upload + parse VC PDF |
| | GET | `/variable-cost` | List VC records (paginated) |
| | GET | `/variable-cost/latest` | Latest VC per plant |
| | PATCH | `/variable-cost/{vc_id}/review` | Mark VC reviewed |
| FSA Constraints | POST | `/fsa-constraints` | Create constraint |
| | GET | `/fsa-constraints` | List (paginated, filterable) |
| | GET | `/fsa-constraints/{record_id}` | Get single |
| | PATCH | `/fsa-constraints/{record_id}` | Update |
| | POST | `/fsa-constraints/{record_id}/review` | Review/approve |
| Landed Cost | POST | `/landed-costs` | Create record |
| | GET | `/landed-costs/latest` | Latest per plant |
| | GET | `/landed-costs` | List (paginated) |
| | GET | `/landed-costs/{record_id}` | Get single |
| | PATCH | `/landed-costs/{record_id}` | Update |
| | POST | `/landed-costs/{record_id}/review` | Review/approve |
| Validation | GET | `/validation/summary` | Cross-entity validation report |
| Audit Logs | GET | `/audit-logs` | List logs (paginated, filterable) |
| Optimization | POST | `/optimization/run` | Trigger LP solver run |
| | GET | `/optimization/runs` | List all runs (paginated) |
| | GET | `/optimization/latest` | Get latest run + detail |
| | GET | `/optimization/runs/{run_id}/allocations` | Get allocations for a run |
| Recommendations | GET | `/recommendations` | List recs (paginated, by plant/severity) |
| Dashboard | GET | `/dashboard/summary` | Aggregated dashboard summary |

---

## Appendix B — Frontend Tab Inventory

| Tab ID | Label | Component | Primary Data Source | Backend Ready? |
|---|---|---|---|---|
| `overview` | Overview | `OverviewTab.jsx` | `optimization` + `daily_fuel` from snapshot | Partial |
| `allocation` | Allocation | `AllocationTab.jsx` | `optimization` from snapshot | Partial |
| `daily` | Fuel Position | `FuelPositionTab.jsx` | `daily_fuel` from snapshot | Ready |
| `registry` | ACQ Registry | `RegistryTab.jsx` | `constraints` from snapshot | Ready |
| `plantstatus` | Plant Status | `PlantStatusTab.jsx` | `optimization` + `daily_fuel` | Partial |
| `entry` | Data Entry | `DailyFuelForm` + `IppAgreementForm` | Writes to API | Partial |
| `documents` | Document Centre | `DocumentCenterTab.jsx` | API + upload | Partial |
| `review` | Review Queue | `ReviewQueueTab.jsx` | Unified queue API | Not Ready |
| `audit` | Audit Logs | `AuditLogTab.jsx` | Audit log API | Ready |
