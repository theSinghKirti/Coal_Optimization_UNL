# Architecture & Data Flow

This document details the modular layout, dependencies, and data flows of the UPRVUNL Coal Optimization & Decision Support Platform (CODSP).

---

## 1. System Components & Text Flow

```
+-------------------------------------------------------------------------------------------------------------------------------+
|                                                        Frontend React Tab                                                     |
+-------------------------------------------------------------------------------------------------------------------------------+
                                                                |
                                                                v
+-------------------------------------------------------------------------------------------------------------------------------+
|                                                       FastAPI Backend Router                                                  |
+-------------------------------------------------------------------------------------------------------------------------------+
                                                                |
                                                                +--------------------------------+
                                                                |                                |
                                                                v                                v
+------------------------------------------------------------------------------------+  +---------------------------------------+
|                                    PostgreSQL Database                             |  |          Document Storage             |
|                                    (Relational Schema)                             |  |       (Git-Ignored Local Path)        |
+------------------------------------------------------------------------------------+  +---------------------------------------+
                                                                |
                                                                v
+-------------------------------------------------------------------------------------------------------------------------------+
|                                                  Text Extraction & Parsers                                                    |
+-------------------------------------------------------------------------------------------------------------------------------+
                                                                |
                                                                v
+-------------------------------------------------------------------------------------------------------------------------------+
|                                                     Manual Review & Approvals                                                 |
+-------------------------------------------------------------------------------------------------------------------------------+
                                                                |
                                                                v
+-------------------------------------------------------------------------------------------------------------------------------+
|                                                   Optimization Precheck Validation                                            |
+-------------------------------------------------------------------------------------------------------------------------------+
                                                                |
                                                                v
+-------------------------------------------------------------------------------------------------------------------------------+
|                                                     OR-Tools LP Solver Engine                                                 |
+-------------------------------------------------------------------------------------------------------------------------------+
                                                                |
                                                                v
+-------------------------------------------------------------------------------------------------------------------------------+
|                                                   Audit Log System Traceability                                               |
+-------------------------------------------------------------------------------------------------------------------------------+
                                                                |
                                                                v
+-------------------------------------------------------------------------------------------------------------------------------+
|                                                   Dashboard Summary & Recommendations                                          |
+-------------------------------------------------------------------------------------------------------------------------------+
                                                                |
                                                                v
+-------------------------------------------------------------------------------------------------------------------------------+
|                                                     APScheduler Core Manager                                                  |
+-------------------------------------------------------------------------------------------------------------------------------+
                                                                |
                                                                v
+-------------------------------------------------------------------------------------------------------------------------------+
|                                                       UPSLDC MOD Monitor                                                      |
+-------------------------------------------------------------------------------------------------------------------------------+
```

---

## 2. Module Responsibilities

1. **Frontend (React 18 / Vite)**:
   - Renders interactive dashboards for coal managers, analysts, and operators.
   - Probes live backend status and executes trigger calls.
   - Gracefully falls back to demo snapshot cards if the backend goes offline.

2. **FastAPI Backend (app.main)**:
   - Configures middleware, registers routes under `/api/v1`, and sets up global CORS policy to accept requests from local frontend origin.
   - Provides JSON validation schemas (Pydantic) and custom error response envelopes.

3. **PostgreSQL DB (SQLAlchemy & Alembic)**:
   - Persists master data (plants, linkages, mines), daily fuel targets, document ingestion logs, audit entries, and scheduler logs.
   - Enforces referential integrity (e.g. Unique constraints on URL hashes and document content hashes).

4. **Document Storage (storage/)**:
   - Stores PDF files on disk inside subdirectories (e.g., `variable_cost_pdf/`).
   - Relies on compute-hash utilities to name and deduplicate files.

5. **Extraction (app.modules.documents.parsers)**:
   - Regex-based and table-mapping parsers that extract plant variable costs and contract caps from unstructured PDFs.

6. **Review / Approval (app.modules.documents.service)**:
   - Holds parsed data in `needs_review=True` status until a fuel cell analyst maps mismatched names and marks them approved.

7. **Validation (app.modules.validation)**:
   - Runs a set of database integrity checks (e.g. checking for missing daily stock or approved landed costs) and outputs issues as blocker lists.

8. **Optimization Solver (app.modules.optimization)**:
   - Formulates the optimization parameters.
   - Translates inputs into an Objective function (minimizing total cost) and constraints (bounds on ACQ, GCV requirements, stock buffers).
   - Calls Google OR-Tools to solve the problem and outputs optimal allocation variables.

9. **Audit Logs (app.modules.audit)**:
   - Appends audit events for tracking updates, trigger calls, and parser outcomes.

10. **Dashboard / Recommendations (app.modules.dashboard)**:
    - Assembles validation state and recommendations metrics into a single API endpoint `/api/v1/dashboard/summary`.

11. **Scheduler & UPSLDC Monitor (app.modules.scheduler)**:
    - Scrapes the UPSLDC MOD list page, compares URL hashes, downloads new MOD reports, and saves them directly as unapproved document archives.

---

## 3. Core Data Flow: Solver Run Trigger

1. Operator clicks **Run Optimization** in the frontend dashboard.
2. Frontend sends `POST /api/v1/optimization/run`.
3. Backend runs validation prechecks:
   - If critical issues exist (e.g., no daily stock date is set):
     - The run is saved as `INCOMPLETE` with blocker issue logs.
     - Optimization halts.
     - HTTP returns run status `INCOMPLETE`.
   - If system is `READY` or only has `WARNINGS`:
     - Pulls approved landed costs, contract ACQ, and daily station stock.
     - Formulates the Linear Programming model.
     - Google OR-Tools solves the model.
     - If optimal:
       - Saves allocation rows.
       - Marks run as `COMPLETED`.
       - Generates recommendations.
4. Frontend reloads and displays solver outcomes or blocker details.
