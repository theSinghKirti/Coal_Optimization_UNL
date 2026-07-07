# Milestone 6B Part 1: Internal Audit Trail Foundation Report

## 1. Files Changed
- [`backend/app/modules/audit/models.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/audit/models.py) — Extended `AuditLog` ORM model mapped fields and types.
- [`backend/app/modules/audit/service.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/audit/service.py) — Reusable internal audit log creator helper `record(...)` supporting new fields.
- [`backend/app/modules/daily_stock/service.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/daily_stock/service.py) — Integrated `DAILY_STOCK_CREATED` audit logs.
- [`backend/app/modules/constraints/service.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/constraints/service.py) — Added `FSA_CONSTRAINT_APPROVED`, `FSA_CONSTRAINT_REJECTED`, and `FSA_CONSTRAINT_MAPPING_CHANGED` events.
- [`backend/app/modules/documents/service.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/documents/service.py) — Configured `DOCUMENT_UPLOADED`, `DOCUMENT_EXTRACTION_STARTED`, `DOCUMENT_EXTRACTION_COMPLETED`, `DOCUMENT_EXTRACTION_FAILED`, and `VARIABLE_COST_APPROVED`.
- [`backend/app/modules/optimization/service.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/optimization/service.py) — Programmed `OPTIMIZATION_RUN_REQUESTED` and run outcome events (`COMPLETED`, `INCOMPLETE`, `FAILED`).
- [`backend/tests/test_audit_foundation.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/tests/test_audit_foundation.py) — New test suite ensuring all audit logs are generated and sanitized correctly.
- [`backend/alembic/versions/5220887f6dc5_extend_audit_logs.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/alembic/versions/5220887f6dc5_extend_audit_logs.py) — Generated schema migration for the `audit_logs` table.

## 2. Migration Details
- **Revision ID:** `5220887f6dc5`
- **Actions:**
  - Renamed column `before` -> `before_state`.
  - Renamed column `after` -> `after_state`.
  - Dropped columns `actor` and `note`.
  - Added columns: `metadata` (JSON), `actor_type` (String), `source` (String), `occurred_at` (DateTime with timezone), `document_id` (UUID, nullable), `optimization_run_id` (UUID, nullable).
  - Configured foreign key constraints pointing to `documents(id)` and `optimization_runs(id)` with `ondelete='SET NULL'`.
- Schema upgrade and downgrade methods are fully implemented and verified via `alembic upgrade head`.

## 3. Audit Table/Model Fields
- `id` — Primary key UUID.
- `action` — Event description (e.g. `DAILY_STOCK_CREATED`).
- `entity_type` — Target entity name (e.g., `"document"`).
- `entity_id` — Target entity primary key UUID.
- `document_id` — Associated document UUID (nullable).
- `optimization_run_id` — Associated run UUID (nullable).
- `before_state` — Snapshot of fields prior to modification (nullable JSON).
- `after_state` — Snapshot of fields after modification (nullable JSON).
- `metadata` — Context data, notes, or warning strings (nullable JSON).
- `actor_type` — Context initiator (`"UNAUTHENTICATED_API"` or `"SYSTEM"`).
- `source` — Initiator type (`"API"` or `"SYSTEM"`).
- `occurred_at` — Event timestamp (DateTime with UTC timezone).

## 4. Audit Events Implemented
- `DAILY_STOCK_CREATED`
- `DOCUMENT_UPLOADED`
- `DOCUMENT_EXTRACTION_STARTED`
- `DOCUMENT_EXTRACTION_COMPLETED`
- `DOCUMENT_EXTRACTION_FAILED`
- `FSA_CONSTRAINT_APPROVED`
- `FSA_CONSTRAINT_REJECTED`
- `FSA_CONSTRAINT_MAPPING_CHANGED`
- `LANDED_COST_APPROVED`
- `LANDED_COST_REJECTED`
- `VARIABLE_COST_APPROVED`
- `OPTIMIZATION_RUN_REQUESTED`
- `OPTIMIZATION_RUN_COMPLETED`
- `OPTIMIZATION_RUN_INCOMPLETE`
- `OPTIMIZATION_RUN_FAILED`

## 5. Backend Flows Instrumented
- **Daily Stock Ingestion:** Triggered on creation. Logs entity snapshots.
- **Documents & Extraction Ingestion:** Tracks upload, extraction start, completion status, or failure logs (including committing logs on file read errors).
- **Manual review/approval:** Logs status transitions for FSA constraints, landed costs, and variable costs. Maps mapping changes separately.
- **Optimization solver runs:** Records validation/solver outcomes and associates them with the run UUID.

## 6. Actor/Source Policy
- Operates under the unauthenticated phase policy:
  - Any event triggered directly via API routers assigns `actor_type = "UNAUTHENTICATED_API"` and `source = "API"`.
  - Internal workflow steps (such as parsers running in background logic) assign `actor_type = "SYSTEM"` and `source = "SYSTEM"`.
- User identities or custom headers are completely avoided in this foundation.

## 7. Snapshot Redaction Policy
- Snapshots include only scalar metrics (such as status, plant identifiers, dates, quantity, and cost values).
- File contents (binary/text streams), request authorization headers, environment variables, credentials, and raw request payloads are strictly omitted from `before_state`, `after_state`, and `metadata` to avoid data leakages.

## 8. Atomicity Approach
- Every service action writes and links its audit records directly inside the active SQLAlchemy session transaction.
- If a database commit fails or an exception occurs, the transaction rolls back cleanly, ensuring no business updates persist without their corresponding audit entries. For exceptions in parsing, the audit record is committed locally to log the failure history.

## 9. Test Results
- All 55 tests passed in the test suite (`pytest` execution completed successfully in `3.20s`).
- Linter checks (`ruff check .`) resolved cleanly with no format or logic violations.

## 10. Confirmation
- No changes were made to the React frontend dashboard code.
- No public audit log retrieval API endpoints (`GET /api/v1/audit-logs`) were implemented, keeping the trail purely backend-internal for this phase.

---
