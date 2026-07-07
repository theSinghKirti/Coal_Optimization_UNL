# UPRVUNL Coal Optimization & Decision Support Platform (CODSP)

An enterprise-grade mathematical planning and optimization platform designed for the Uttar Pradesh Rajya Vidyut Utpadan Nigam Limited (UPRVUNL) to minimize the blended landed cost of coal across utility thermal power stations while fully satisfying fuel supply agreements (FSA), logistics, environmental, and boiler quality constraints.

---

## 1. Problem Statement & Objective

**Problem:** UPRVUNL manages multiple coal-fired power stations with varying load requirements, grid dispatch priorities, and environmental/technical constraints. Procuring coal involves complex negotiations, multiple supply mine linkages (FSA, Bridge Linkage), and variable transportation costs. Historically, sub-optimal allocation led to increased fuel costs or technical inefficiencies.

**Objective:** Minimize the total blended landed cost of coal across all UPRVUNL stations by dynamically optimizing quantity allocations from available sources (mines and spot markets) while complying with contract caps (ACQ), logistics, stock cover safety levels, and technical blending criteria.

---

## 2. Tech Stack

- **FastAPI Backend**: Python 3.11 asynchronous web framework, SQLAlchemy 2.0 ORM, Alembic migrations, PostgreSQL database.
- **LP Solver**: Google OR-Tools (Linear Programming) solver.
- **Frontend Dashboard**: React 18, Vite, Tailwind CSS, Recharts.
- **Local Storage**: File-based document archival for PDFs and parsed agreements.
- **Background Scheduler**: APScheduler integration for regular tasks and monitoring.

---

## 3. Major Features

1. **LP Solver Allocation Engine**: Automatically calculates lowest-cost procurement plans.
2. **Precheck Verification**: Pre-run checks validate daily stock, ACQ registry availability, and approved landed costs before letting a run trigger.
3. **Audit Log System**: Complete traceability on all data updates, uploads, approvals, and monitor triggers.
4. **Document Ingestion Workflow**: PDF document archival with manual review and approval safeguards.
5. **UPSLDC MOD Monitor**: Autonomous tracking of UPSLDC Variable Cost reports with secure PDF archival.

---

## 4. Architecture Overview

```
                        +---------------------------------------+
                        |           React Frontend              |
                        +-------------------+-------------------+
                                            | REST API / JSON
                                            v
                        +-------------------+-------------------+
                        |          FastAPI Backend              |
                        +---+---------------+---------------+---+
                            |               |               |
                            v               v               v
                   +--------+---+    +------+-----+    +----+------+
                   | OR-Tools   |    | PostgreSQL |    | Local File|
                   | LP Solver  |    | Database   |    | Storage   |
                   +------------+    +------------+    +-----------+
```

### End-to-End Workflow
1. **Inputs**: Daily stock balance, PLF, and generation targets are inputted.
2. **Archival**: Landed cost rules and FSA contracts are uploaded as PDFs and stored.
3. **Validation**: Pre-run precheck verifies if any critical data is missing.
4. **Solve**: The LP solver runs, optimizing allocations and outputting suggestions.
5. **Monitor**: The UPSLDC monitor regularly checks the external listing page for new MOD stacks and archives them safely for operator review.

---

## 5. Repository Structure

```
.
├── backend/                  # FastAPI codebase
│   ├── app/                  # Main modules (optimization, documents, audit, etc.)
│   ├── alembic/              # Database migration scripts
│   └── tests/                # Automated pytest suite
├── frontend/                 # React dashboard
│   ├── src/                  # Components, charts, and application hook
│   └── dist/                 # Compiled production build output
├── storage/                  # Local git-ignored document archive
│   └── documents/            # Uploaded and archived PDFs
└── docs/                     # Project documentation
    ├── archive/              # Moved phase and milestone reports
    ├── reference/            # Technical blueprints and specifications
    ├── PROJECT_SUMMARY.md    # Executive milestone & feature summary
    ├── ARCHITECTURE.md       # Complete system module flow
    ├── DEMO_WALKTHROUGH.md   # Step-by-step user-flow guide
    ├── DEPLOYMENT_READINESS.md# Infrastructure deployment guide
    └── FINAL_PROJECT_STATUS.md# Final status check & classification
```

---

## 6. Environment & Setup

### Backend Setup
1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Set up a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Run Alembic migrations:
   ```bash
   alembic upgrade head
   ```
4. Start the backend server:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
*Swagger docs location:* `http://127.0.0.1:8000/docs`

### Frontend Setup
1. Navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Compile the production bundle:
   ```bash
   npm run build
   ```
4. Launch the local dev server:
   ```bash
   npm run dev
   ```

---

## 7. Testing

Run all backend unit, integration, and mock scheduler tests:
```bash
cd backend
pytest
```

---

## 8. UPSLDC MOD Monitor Behavior & Safety

- **Disabled by Default**: The scheduler and monitor are disabled in general configuration settings and only active in test configurations or explicit cron environments.
- **Audit-Only / Pending Review**: Downloaded MOD PDFs are stored with `needs_review=True` and `review_status="pending_review"`. They do not modify active variable costs or trigger optimization recalculation automatically.

---

## 9. Key Documentation Links

- **Milestone & Project Summary**: [docs/PROJECT_SUMMARY.md](file:///c:/Users/itisa/Desktop/mdsir/docs/PROJECT_SUMMARY.md)
- **Architecture & Data Flow**: [docs/ARCHITECTURE.md](file:///c:/Users/itisa/Desktop/mdsir/docs/ARCHITECTURE.md)
- **Executive Demo Walkthrough**: [docs/DEMO_WALKTHROUGH.md](file:///c:/Users/itisa/Desktop/mdsir/docs/DEMO_WALKTHROUGH.md)
- **Deployment Checklist**: [docs/DEPLOYMENT_READINESS.md](file:///c:/Users/itisa/Desktop/mdsir/docs/DEPLOYMENT_READINESS.md)
- **Final Status Report**: [docs/FINAL_PROJECT_STATUS.md](file:///c:/Users/itisa/Desktop/mdsir/docs/FINAL_PROJECT_STATUS.md)
