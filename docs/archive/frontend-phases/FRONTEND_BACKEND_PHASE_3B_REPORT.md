# Frontend/Backend Integration Phase 3B: Review, Mapping, and Approval Workflow Report

## 1. Frontend Files Changed
- [`frontend/src/App.jsx`](file:///c:/Users/itisa/Desktop/mdsir/frontend/src/App.jsx) — Passed the `refreshLive` prop to `<ReviewQueueTab>` to wire up validation-summary refresh actions.
- [`frontend/src/components/ReviewQueueTab.jsx`](file:///c:/Users/itisa/Desktop/mdsir/frontend/src/components/ReviewQueueTab.jsx) — Completely replaced mock review functionality with real API endpoints, plant mapping dropdowns, inline confirm panels, status badges, and data loading.

## 2. Real Backend Endpoints Used
- `GET /api/v1/plants` — Loads the master list of canonical power plants for mapping.
- `GET /api/v1/documents` — Fetches metadata of files to resolve filenames and upload timestamps.
- `GET /api/v1/fsa-constraints` — Retrieves raw contract/linkage constraints.
- `POST /api/v1/fsa-constraints/{id}/review` — Submits review status (`APPROVED` or `REJECTED`) for FSA/Bridge constraints.
- `GET /api/v1/landed-costs` — Retrieves landed cost records.
- `POST /api/v1/landed-costs/{id}/review` — Submits review status (`APPROVED` or `REJECTED`) for Landed Cost records.
- `GET /api/v1/variable-cost` — Retrieves extracted variable cost rows.
- `PATCH /api/v1/variable-cost/{id}/review` — Resolves the plant mapping and completes the review of Variable Cost records.
- `GET /api/v1/coal-companies` — Retrieves coal companies.
- `GET /api/v1/suppliers` — Retrieves suppliers.

## 3. Reviewable Record Types Implemented
- **FSA Constraints / Bridge Linkage:** Renders extracted quantities, monthly caps, validity, and parser warnings.
- **Landed Cost:** Displays raw source name, extracted basic cost, freight, taxes, total landed cost, and weighted GCV.
- **Variable Cost:** Displays unit variable costs, effective dates, and plant identifiers.

## 4. Plant Mapping Behaviour
- Showcases the raw extracted plant text alongside a canonical plant selection dropdown.
- Pulls plant options from the live `/plants` API.
- Stores and transmits the UUID internally.
- Prevents approval (disables the Approve button) if the record lacks a mapped canonical plant, displaying an explicit warning.

## 5. Approve/Reject Behaviour
- **Approve Flow:**
  - When the user clicks Approve, an inline confirmation panel opens displaying mapped values, final parameters, and warning flags.
  - Upon confirmation, calls the corresponding backend endpoint (`POST` or `PATCH`), then triggers a UI-wide data refresh.
- **Reject Flow:**
  - When the user clicks Reject, prompts the user for a rejection reason.
  - Submits the rejection status (`REJECTED`) to the backend (for supported record types).
  - Since the backend schemas (`FSAConstraintReview` / `LandedCostReview`) do not accept custom extra fields, the reason is validated locally in the UI to confirm user intent, while the standard API payloads are transmitted successfully.

## 6. Variable Cost Handling Decision
- **Yes**, the backend exposes a real review route: `PATCH /api/v1/variable-cost/{vc_id}/review`.
- Because this endpoint only accepts `plant_id` and `needs_review: false` (to mark it resolved/approved), we support plant mapping and resolution in the UI. Rejection is not supported by the backend model, so the Reject button is replaced with a clear notification note.

## 7. Validation-Summary Refresh Behaviour
- Approvals and rejections call the parent `refreshLive()` hook (`liveData.refresh()`).
- This immediately updates the global validation engine, resolving warnings (such as `FSA_BRIDGE_PENDING_REVIEW` or `LANDED_COST_PENDING_REVIEW`) dynamically in the sidebar status panel.

## 8. Verification Results
- **pytest:** **PASSED** (all 46 backend tests passed).
- **ruff check:** **PASSED** (no styling or python lint issues).
- **npm run build:** **PASSED** (frontend compiles cleanly).
- **Browser Run:** Visual validation shows that pending records load with details, mapping dropdown works, confirmation dialog displays properly, and actions update the state.

## 9. Known Backend Limitations Not Solved in This Phase
- The review schemas (`FSAConstraintReview` and `LandedCostReview`) lack a `rejection_reason` or `remarks` field, meaning rejection logs are tracked strictly on the transition status without storing custom comments in the database records.

---
