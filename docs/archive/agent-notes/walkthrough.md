# Local Verification Walkthrough

The UPRVUNL Coal Optimization & Decision Support Platform (CODSP) has been successfully run locally. Below are the details and status of all services.

## Services Status

| Service | Address | Status | Verification |
| --- | --- | --- | --- |
| **PostgreSQL Database** | `localhost:5432` | **Online** (Docker Container) | Managed by Docker Desktop, mapped to port 5432 |
| **FastAPI Backend** | `http://127.0.0.1:8001/` | **Online** (Port 8001) | Healthcheck endpoint (`/api/v1/health`) is ok |
| **Vite React Frontend** | `http://localhost:5173/` | **Online** (Port 5173) | Frontend connects successfully and displays live status |

---

## Service Verification & Access

### 1. PostgreSQL Database
The PostgreSQL instance is running in a Docker container on port `5432`:
- **Container Name:** `codsp_postgres`
- **Database:** `codsp_db`
- **Status:** Healthy

Database migrations (`alembic upgrade head`) and master data seeding (`scripts.seed`) have been successfully executed against this database.

### 2. FastAPI Backend
The FastAPI server is running on port `8001` in the background:
- **API Base URL:** `http://127.0.0.1:8001/api/v1`
- **Swagger Documentation:** [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)

### 3. React Frontend
The Vite development server is serving the UI on port `5173`:
- **Vite Dev URL:** [http://localhost:5173/](http://localhost:5173/)
- **Live Status Indicator:** Renders `LIVE` (teal badge), confirming successful connection and polling to the FastAPI backend API on port `8001`.

---

## Verification Screenshot

Below is a screenshot of the **Live Backend Status** panel on the frontend, showing that it is successfully fetching the status from the FastAPI backend and database:

![Live status verification](C:/Users/itisa/.gemini/antigravity-ide/brain/a5891d42-33be-4fc1-a83a-49f3358c63e6/initial_load_1783356875407.png)

> [!NOTE]
> Since the database was freshly migrated and seeded, there are currently no daily stock records or other operational inputs. As a result, the backend validation precheck correctly returns an **INCOMPLETE** status, and the optimization run displays **OPTIMIZATION INCOMPLETE** because the inputs are missing.

---

## Phase 3B Integration & Verification Walkthrough

The manual document review queue mapping and approval workflow has been successfully integrated and verified.

### Review Queue UI Features:
1. **Pending Queue:** Lists all extracted constraints, landed costs, and variable cost rows that are pending review, unmapped, rejected, or flagged.
2. **Plant Mapping Dropdowns:** Allows selecting canonical plants dynamically from `/plants`.
3. **Approve Actions:** Triggers inline confirmation and API review updates to the backend.
4. **Rejection Actions:** Prompts for a local rejection reason and marks the backend record `REJECTED`.
5. **Real-time Status Refreshes:** Refreshes live dashboard stats and validation summaries dynamically.

### Verification Screenshot:
Below is a screenshot of the pending review queue containing a freshly created constraint task in the dashboard:

![Review Queue Pending State](C:/Users/itisa/.gemini/antigravity-ide/brain/a5891d42-33be-4fc1-a83a-49f3358c63e6/review_queue_init_1783376042852.png)

---

## Milestone 6B Part 1: Internal Audit Trail Foundation Walkthrough

The backend-internal append-only audit log system has been successfully implemented and verified.

### Walkthrough & Completed Actions:
1. **Schema Migration:** Database migrated cleanly to upgrade the `audit_logs` table (adding `metadata`, `actor_type`, `source`, `occurred_at`, `document_id`, `optimization_run_id` fields).
2. **Internal Audit Service:** Built a reusable `audit_service.record(...)` method.
3. **Daily Stock & Ingestion Logging:** Logs the creation of daily stock logs (`DAILY_STOCK_CREATED`).
4. **Documents & Extraction Logs:** Tracks document uploads, parse starts, extraction completions, and extraction failures.
5. **Review approvals/rejections:** Records outcomes for constraints, landed costs, and variable costs. Logs mapping updates as separate event entries.
6. **Solver Execution Tracking:** Audit events are created when runs are requested and completed.
7. **Redaction Check:** Asserted that no file contents, request headers, credentials, or secrets leak into audit logs.
8. **Test Verification:** Configured 9 new dedicated integration tests inside `test_audit_foundation.py`. All 55 backend tests passed successfully.

---

## Milestone 6B Part 2: Read-Only Audit Log API Walkthrough

Exposed read-only REST APIs for retrieving and filtering the append-only audit trail logs.

### Completed Actions & Verification:
1. **API Endpoints Exposed:**
   - `GET /api/v1/audit-logs` (Paginated list endpoint)
   - `GET /api/v1/audit-logs/{audit_log_id}` (Individual detail endpoint)
2. **Filters & Sorting Supported:** Query parameters support filtering by action, entity type, entity UUID, document UUID, optimization run UUID, and occurred dates. Custom pagination yields `page`, `page_size`, `total`, and `has_next_page` parameters.
3. **Stable Sorting Order:** Outputs sorted strictly by `occurred_at DESC` and fallback `id DESC`.
4. **Enforced Boundary Checks:** The page size limits to `100` and throws validation errors (422) if exceeded.
5. **Detail Endpoint Error Checks:** Returns a clean `404 Not Found` if a queried UUID does not match any database record.
6. **Data Safety Redaction Layer:** Integrated a recursive sanitizer validator in Pydantic serialization schemas. Automatically filters out sensitive keys/values (passwords, JWTs, secrets, bytes, file bytes, PDF text, headers, and request bodies) while keeping business fields (status, plant_id, quantity, cost, etc.).
7. **Verify Mutation Exclusions:** Confirmed that POST/PUT/PATCH/DELETE endpoints do not exist for the resource.
8. **Final Backend Test Green Suite:** Appended 15 dedicated tests covering API requirements. All **56** tests passed successfully.

---

## Milestone 8A Part 1: Read-Only Dashboard Summary API Walkthrough

Exposed a stable backend endpoint `/api/v1/dashboard/summary` for the frontend Overview dashboard tab.

### Completed Actions & Verification:
1. **Endpoint Implementation:** Exposed `GET /api/v1/dashboard/summary` (tagged `Dashboard`) returning detailed metadata, validation, optimization, coverage, and next actions.
2. **Metadata & Status:** Dynamically outputs system status (`READY`, `WARNING`, `INCOMPLETE`) derived directly from the validation summary service.
3. **Validation Summary Blocker Limit:** Limits top blockers to 5, exposing only code, category, message, and affected counts without exposing internal exceptions.
4. **Optimization Snapshot Metrics:** Correctly displays optimization run details. Nulls out metrics for incomplete or missing runs, and populates real metrics (`plants_covered_count`, `total_demand_mt`, `total_allocated_mt`, `market_top_up_mt`, `total_estimated_cost`, `allocation_count`) for completed runs.
5. **Operational Data Coverage:** Computes exact active plant, daily stock, FSA constraint, landed cost, and variable cost counts directly from DB schemas.
6. **Deterministic Next Actions:** Evaluates coverage and validation status to produce actionable items (such as entering daily stock, reviewing constraints, resolving landed costs, etc.) with priority levels.
7. **Suite Solidification:** Added 4 new integration tests covering all requirements. Running backend test suite is 100% green (**60** tests passed). All linter checks passed.



