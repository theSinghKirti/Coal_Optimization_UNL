# Project Summary

## 1. Executive Summary
- **Problem Statement**: Minimizing the blended landed cost of coal across thermal power stations is mathematically complex due to varying linkages, transportation modes, logistics restrictions, take-or-pay clauses, and coal quality properties (GCV and ash limits).
- **Architecture Overview**: The platform consists of a FastAPI backend using Python 3.11, OR-Tools (LP Solver), PostgreSQL DB, and local file storage, with a responsive React 18 / Vite frontend dashboard.
- **Operational Workflow**: Operators upload daily coal targets and contract updates, validation checks verify data completeness, and the linear programming (LP) engine solves for optimal allocations, monitored safely by an automated UPSLDC PDF parser.

---

## 2. Completed Milestones (Backend)

| Milestone | Title | Focus & Summary (2-4 lines max) |
| :--- | :--- | :--- |
| **M1** | Database Foundation | Established PostgreSQL schemas, ORM models for plants, linkages, stock, audit logs, and set up Alembic migrations. |
| **M2** | Master Data APIs | Implemented CRUD APIs for plant records, mine details, shipping agencies, and plant-level aliases for flexible naming. |
| **M3** | Daily Stock | Built inputs for daily coal stock balance, receipts, MU generation targets, and PLF, with duplicate prevention. |
| **M4** | Document System | Created static PDF file archival system supporting Linkage agreements, FSA contracts, and Government Orders. |
| **M5** | Ingestion & LP Solver | Connected GCV properties, landed costs, and ACQ registry data to Google OR-Tools to solve the blended cost LP model. |
| **M6** | Auditing & Review | Implemented a system-wide audit logging mechanism and a manual verification queue for incoming document extractions. |
| **M7** | Performance Tuning | Optimized LP solving times, added bulk DB insert operations, and improved query latency under high load. |
| **M8** | Read-Only APIs | Created dashboard summary statistics endpoints and deterministic recommendation engines to feed the frontend. |
| **M9** | Scheduler & Monitor | Set up the APScheduler framework and built the UPSLDC MOD stack scraper and automatic PDF downloader. |

---

## 3. Completed Frontend Phases

| Phase | Title | Summary (2-4 lines max) |
| :--- | :--- | :--- |
| **Phase 0** | Core Layout | Built Sidebar, plant key ribbon, custom CSS variables theme, and active role-simulation selectors. |
| **Phase 1** | Forms & Status | Implemented Daily Fuel input form, dynamic validation error toasts, and live connection status indicators. |
| **Phase 2** | Prechecks & Trigger | Created the Optimization Readiness Precheck panel, validation blocker alerts list, and manual trigger button. |
| **Phase 3** | Documents & Review | Built file upload portals, extraction logs tracker, and the manual Mapping & Approval review queue workspace. |
| **Phase 4** | Overview Live Data | Connected the Overview metrics cards, shortfall alerts, and recommendation cards to the backend's live APIs. |

---

## 4. Current V1 Capabilities
- **Procurement Cost Optimization**: Multi-source linear programming minimizes landed costs under ACQ registry limitations.
- **Operational Data Ingest**: Full manual entry logs for daily station operations.
- **Traceable Audit Logging**: Immutable record of changes for compliance.
- **Readiness Safeguards**: Prevents running optimization if required data is missing.
- **UPSLDC Monitor**: Auto-detects and downloads external MOD stacks to local storage.

---

## 5. Key Safety Controls
- **Review Safeguard**: All automated extractions and downloads (such as PDF files from UPSLDC) remain `PENDING_REVIEW` and require an analyst to manually map and approve before they affect active variables.
- **LP Solver Fail-Safe**: If validation fails or data is incomplete, the system marks the run `INCOMPLETE` and refuses to output incorrect allocations.
- **Read-Only Enforcements**: Audit logs, recommendation views, and scheduler statuses are strictly read-only and have no mutating HTTP methods.

---

## 6. Intentionally Deferred Features
- **Automatic Optimization Execution**: Kept manual trigger only to ensure operator oversight.
- **Direct Database Update from Monitor**: Monitor PDF downloads do not update variable costs directly; must go through manual approval.
- **Multi-User RBAC and Authentication**: Left for enterprise single sign-on integration in V2.

---

## 7. Current Known Limitations
- **PDF Scraper Ambiguities**: Title formats that don't match typical date ranges will result in null effective dates, requiring manual correction.
- **Single Process Scheduler**: APScheduler runs locally inside the main backend web server process, requiring single-node deployment to avoid duplicate job triggers.
- **Local File Path Dependency**: Document storage requires write access to the local path configured in settings.
