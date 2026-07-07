# Executive Demo Consistency Report

This report summarizes the inspection and resolution of stale/hard-coded optimization status and plant count values on the frontend dashboard to ensure absolute consistency with live backend data.

---

## 1. Stale / Hard-Coded Operational Values Found

| Value Found | Location / Component | Impact | Corrective Action |
| :--- | :--- | :--- | :--- |
| `"Run status: OPTIMAL"` | `App.jsx` (Topbar Meta) | Conflicted with the live backend's validation precheck status (`INCOMPLETE`) | Replaced with dynamic, live backend status. Shows `INCOMPLETE`, `COMPLETED`, `No Optimization Run Yet` (replaces `"NO RUN"`), or `BACKEND OFFLINE` based on live API. |
| `"7 plants covered"` | `App.jsx` (Topbar Meta) | Hardcoded display of plant counts from static `demoSnapshot.json` | Updated to read `liveData.dashboardSummary.optimization.plants_covered_count` from live backend when connected. |
| `optimization.status.toUpperCase()` | `App.jsx` (Sidebar Status Pill) | Showed `"OPTIMAL"` status from demo snapshot | Replaced with live backend run status, displaying color-coded pills corresponding to live state. |
| `"LP · Optimal"` | `PlantStatusTab.jsx` (Panel Badge) | Claimed optimal status in a panel using offline demo data | Relabeled the badge to `"DEMO DATA"`. |
| `"Stations Modelled"` | `PlantStatusTab.jsx` (Fleet KPI card) | Statically showed 7 stations modeled from the demo snapshot | Relabeled to `"Stations Modelled (DEMO)"` and added a prominent purple banner explaining that the tab metrics are based on demo snapshot data. |
| `Savings, Fleet Saving, Cheapest Source` | `PlantStatusTab.jsx` (Fleet KPIs) | Displayed static demo calculation labels without indication | Relabeled all KPI cards in the Fleet KPI strip with `(DEMO)` suffixes. |

---

## 2. Files Changed

### Frontend
1. **[App.jsx](file:///c:/Users/itisa/Desktop/mdsir/frontend/src/App.jsx)**
   - Passed `liveData` prop to the `PlantStatusTab` component.
   - Refactored the global topbar to read optimization run status and plant covered count from `liveData.dashboardSummary` (live backend API) dynamically.
   - Refactored the sidebar status pill to dynamically evaluate and display current backend run status: `COMPLETED`, `INCOMPLETE`, `No Optimization Run Yet` (replaces `"NO RUN"`), or `BACKEND OFFLINE`.
2. **[PlantStatusTab.jsx](file:///c:/Users/itisa/Desktop/mdsir/frontend/src/components/PlantStatusTab.jsx)**
   - Updated component parameters to receive the `liveData` prop.
   - Implemented a live run status alert banner block at the top of the tab corresponding to connection/solver statuses (`BACKEND OFFLINE`, `No Optimization Run Yet`, `LIVE RUN STATUS: COMPLETED / OPTIMAL`, `OPTIMIZATION INCOMPLETE`).
   - Added a clear purple `DEMO DATA` warning banner.
   - Relabeled all fleet KPI strip elements (`Fleet Saving`, `Plants Behind Tied IPP`, `Stations Modelled`, `Cheapest Source`) with a `(DEMO)` marker to distinguish them from live data.
   - Relabeled the panel header badge of the optimized allocation table to `"DEMO DATA"`.

---

## 3. Live Backend Data Integrations vs. Demo-Labeled Items

### Live Backend Data (Live APIs)
- **Topbar Run Status Badge**: Dynamically represents the live backend solver status (e.g. `INCOMPLETE` / `COMPLETED` / `No Optimization Run Yet`).
- **Topbar Covered Plants Count**: Displays the actual count of plants covered from the last successful solver run.
- **Sidebar Status Pill**: Color-coded and text-driven by the live solver execution state.
- **Readiness Precheck Banner**: In `Overview` and `Allocation` tabs, directly consumes live validation/coverage APIs.
- **Precheck & Run Action Controller**: In `Allocation` tab, live pre-run validation checks, blocker alerts, and "Run Optimization" trigger connect to real backend endpoints.
- **Run Status Banners**: At the top of `PlantStatusTab`, displays a real-time status alert banner driven by live backend connectivity and optimization run checks.

### Demo-Labeled Components (Uses Cached Snapshot)
- **Overview Tab Comparison Charts & Metrics**: All charts (Cost, PLF, Stock, Allocation) and KPI cards are explicitly badge-labeled as `DEMO DATA`.
- **Allocation Tab Cost/ACQ Visualizations & Per-Plant Cards**: Labeled with a prominent warning divider and `DEMO DATA` badges.
- **Plant Status Per-Plant Allocation Table & Fleet KPIs**: Marked with the purple `DEMO DATA` banner, `(DEMO)` labels, and a `DEMO DATA` panel badge.

---

## 4. Verification Results

All local verification checks ran and completed successfully:
- **Frontend Build**: `npm run build` compiled without errors.
- **Backend Test Suite**: `pytest` passed 97/97 tests (including mock monitor and archival tests).
- **Backend Linting**: `ruff check` succeeded with zero violations.
