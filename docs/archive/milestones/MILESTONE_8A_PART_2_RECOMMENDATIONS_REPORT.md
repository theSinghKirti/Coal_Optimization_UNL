# Milestone 8A Part 2: Deterministic Recommendations API Report

## 1. Files Changed
- [`backend/app/modules/recommendations/schemas.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/recommendations/schemas.py) — Created robust Pydantic schemas for the recommendations response (`RecommendationItem`, `RecommendationLatestSummary`).
- [`backend/app/modules/recommendations/router.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/recommendations/router.py) — Registered the new GET `/api/v1/recommendations/latest` endpoint under the `Recommendations` tag.
- [`backend/app/modules/recommendations/service.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/recommendations/service.py) — Implemented `build_latest_recommendations(db)` on-demand deterministic generator function.
- [`backend/tests/test_latest_recommendations.py`](file:///c:/Users/itisa/Desktop/mdsir/backend/tests/test_latest_recommendations.py) — Created 7 integration tests covering safe empty database responses, daily stock grouping, constraint rules, landed cost/variable cost missing and review states, incomplete/completed optimization runs, stable key checks, severity sorting, and audit-less GET operations.

## 2. Route Reused
- **`GET /api/v1/recommendations/latest`** — Created a fresh endpoint maps directly to recommendations router mapped at `/api/v1/recommendations/latest` with `Recommendations` route tag.

## 3. Exact Response Schema
The response payload contains:
- `generated_at`: datetime
- `system_status`: Literal `"READY"`, `"WARNING"`, `"INCOMPLETE"`
- `recommendation_count`: int
- `recommendations`: list[`RecommendationItem`]
  - Each item contains: `recommendation_key`, `category`, `severity`, `title`, `message`, `recommended_next_action`, `related_module`, `affected_plant_id`, `affected_plant_name`, `affected_company`, `affected_count`, `source_entity_type`, `source_entity_ids`, `optimization_run_id`, `status_context`, and `created_from_data_as_of`.

## 4. Deterministic Recommendation Rules
- **Daily Stock**: Groups all plants missing latest daily stock into a single CRITICAL category recommendation.
- **Constraints**: Warns on pending review, rejected, or expired bridge linkage constraints with precise actions. Raises critical warnings if constraints are unmapped.
- **Landed Costs**: Evaluates plants missing landed cost coverage or with pending/needs-review/rejected cost records.
- **Variable Costs**: Flags missing coverage or pending reviews.
- **Optimization**: Warns of incomplete run blockers or prompts execution if the state is fully ready.
- **Sorting**: Ordered deterministically by severity (`CRITICAL` -> `WARNING` -> `INFO`), then by category, then by stable key.

## 5. Stable Key Strategy
Recommendation keys are derived deterministically using constants combined with affected identifiers or scopes:
- `DAILY_STOCK_MISSING_ACTIVE_PLANTS`
- `FSA_BRIDGE_UNMAPPED_CONSTRAINT_<constraint_id>`
- `FSA_BRIDGE_PENDING_REVIEW_<constraint_id>`
- `LANDED_COST_PENDING_REVIEW_<landed_cost_id>`
- `OPTIMIZATION_INCOMPLETE_<run_id>`

## 6. Traceability Strategy
- Standard fields `source_entity_type` (e.g. `"fsa_constraint"`, `"landed_cost"`, `"plant"`, `"optimization_run"`) and `source_entity_ids` contain original database identifiers to enable immediate click-through tracking on the future UI.
- Allocations/Run recommendations correctly link their parent `optimization_run_id`.

## 7. Incomplete-Run Behaviour
- Highlights validation blockers using the latest run ID.
- Never outputs fake metrics or cost totals.

## 8. No-Run Behaviour
- Returns an INFO recommendation to execute optimization only if inputs are validated and ready (`system_status == "READY"` and `len(active_plants) > 0`). Otherwise, does not suggest solver execution.

## 9. Completed-Run Behaviour
- Only generates allocation warning metrics (market top-ups required, constraint utilization bounds) when backed by real allocations.
- Never fabricates baseline differences or cost savings.

## 10. Test Coverage and Final Results
- Pytest execution results:
  - **Total Passed:** 67 tests.
  - **Execution Time:** 4.12 seconds.
- Linter verification (`ruff check .`) resolved with **0 issues**.

## 11. Confirmation
- React frontend files (`frontend/`) were completely untouched.
- No recommendation persist tables, scheduler jobs, solver parameters, or parser functions were modified.
- Operations are read-only and generate no audit logs.

---
