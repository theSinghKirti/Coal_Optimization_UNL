# Executive Demo Walkthrough Guide

This step-by-step guide walks you through a comprehensive demonstration of the UPRVUNL Coal Optimization & Decision Support Platform (CODSP).

---

## Step 1: Open the Dashboard Overview
1. Start both the frontend and backend servers.
2. Open your web browser and navigate to `http://localhost:5173/`.
3. The platform opens on the **Overview** tab, showcasing a high-level operational summary.

---

## Step 2: Understand "LIVE BACKEND DATA" vs. "DEMO DATA"
- Point out the **Live Backend Status** panel at the top. This section reads from the active PostgreSQL database via `/api/v1/dashboard/summary`.
- Look at the cards and charts below. Note the distinct violet **DEMO DATA** badges and banners. Explain that the charts and comparison metrics show the offline, simulated baseline snapshot, while the top panel represents live system data.
- If the backend is turned off, a red **BACKEND OFFLINE** banner appears, and the app gracefully falls back to the demo snapshot.

---

## Step 3: Inspect Operational Readiness
- Look at the **Operational Readiness** card inside the live summary panel.
- Explain the current readiness status (`READY`, `WARNING`, or `INCOMPLETE`).
- Point out the blocker list. If critical inputs are missing, they will be listed here with clear descriptions (e.g. `MISSING_DAILY_STOCK` or `MISSING_APPROVED_LANDED_COST`).

---

## Step 4: Enter Daily Fuel Stock
1. Select the **Data Entry** tab on the sidebar navigation.
2. In the **Daily Fuel Entry Form**, select a power station (e.g., *Anpara*), enter coal stock quantities, receipts, PLF %, and generation targets.
3. Click **Submit Fuel Position**. A notification confirms that the record was successfully written to the database.

---

## Step 5: Upload a Document
1. Go to the **Document Centre** tab.
2. Under "Upload Procurement Document", choose a file type (e.g., *FSA / Bridge Linkage Contract* or *Landed Cost Document*).
3. Drag and drop or browse to select a PDF contract file.
4. Click **Upload & Process Document**.

---

## Step 6: Verify Extraction & Tracking
1. Still in the Document Centre, look at the **Document Upload Logs** table.
2. Observe the status transitions from `PENDING` to `PARSING` and then `SUCCESS` or `FAILED`.
3. Point out that the document has been archived in the git-ignored local storage and its content hash has been verified to prevent duplicates.

---

## Step 7: Open the Review Queue
1. Navigate to the **Review Queue** tab.
2. Explain that to protect the optimization engine, newly uploaded contracts are placed in a review state (`needs_review=True`, `review_status="pending_review"`) and are not active yet.

---

## Step 8: Map Plant Naming Variations
1. Find your uploaded contract in the Review Queue.
2. If the parser encountered a name variation (e.g. "Anpara Thermal Power" instead of the canonical "Anpara"), it will mark the match confidence low.
3. Click the plant drop-down select element next to the item to map it to the canonical plant.

---

## Step 9: Approve/Reject the Record
1. Click **Approve** on the mapped row.
2. Confirm the action. This updates the DB record status to `approved`, clearing the data gap and making it available to the optimization solver.
3. Try clicking **Reject** on an invalid document to show how it is flagged as rejected and excluded from all solver models.

---

## Step 10: Observe Validation Status Refresh
1. Return to the **Overview** or **Allocation** tab.
2. Click **Refresh** inside the live panel.
3. Observe how the blocker count has decreased and the readiness status has updated (e.g., transitioning from `INCOMPLETE` to `READY` once the required daily stock and landed cost data are filled).

---

## Step 11: Trigger Optimization Solver
1. Go to the **Allocation** tab.
2. Review the live pre-run validation checks status.
3. Click the green **Run Optimization** button.

---

## Step 12: View Solver Fail-Safe (INCOMPLETE State)
- *If any critical blockers remain unapproved:* Show the warning message that appears. Point out that the system saved the run status as `INCOMPLETE`, explaining that the model refused to solve or output incorrect allocations due to missing required parameters.

---

## Step 13: Inspect Completed Allocation Output
- *Once all validation blockers are cleared:* Trigger the solver.
- The solver successfully executes Google OR-Tools in the backend, saving the run status as `COMPLETED`.
- Look at the **Allocation Results** panel. Expand the plant cards to inspect allocated quantities, unit costs, and ACQ utilization percentages.

---

## Step 14: Show Dynamic recommendations
1. On the **Overview** tab, scroll to the **Recommended Next Actions** panel.
2. Observe the list of recommended actions generated dynamically from the live run (e.g., instructions to shift allocation to avoid under-lifting penalties or e-auction premiums).

---

## Step 15: Verify Audit Log Traceability
1. Go to the **Audit Logs** tab on the sidebar.
2. Point out the scrollable list of system events.
3. Highlight the entries corresponding to your actions: `DOCUMENT_UPLOADED`, `DOCUMENT_APPROVED`, `OPTIMIZATION_RUN_STARTED`, `OPTIMIZATION_RUN_COMPLETED`. Explain how this log provides absolute historical traceability.

---

## Step 16: Check Scheduler Status
1. Observe the **Scheduler Status** panel in the bottom-left sidebar (or go to the health check status).
2. Point out that the status shows the scheduler is active and running heartbeats.

---

## Step 17: Explain UPSLDC Scraper Intake & Manual Approval Safeguard
1. Describe how the UPSLDC MOD scraper runs in the background.
2. Emphasize that when the monitor detects and downloads a new MOD report PDF, the file is safely archived as a document but marked `needs_review=True`.
3. Explain that the new variable costs do not enter active optimization until an operator approves them in the Review Queue.
