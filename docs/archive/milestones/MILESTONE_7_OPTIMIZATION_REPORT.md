# Milestone 7: Optimization Engine and Allocation Persistence Report

This report outlines the implementation details for the deterministic coal-allocation optimization engine and persistence workflow.

---

## 1. Files Changed & Added

- **Added**:
  - [`alembic/versions/a8b9c0d1e2f7_add_optimization_fields.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/alembic/versions/a8b9c0d1e2f7_add_optimization_fields.py): Database schema migration to support run validation summaries, dates, and allocation metadata.

- **Modified**:
  - [`app/modules/optimization/models.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/optimization/models.py): Completed `OptimizationRun` and `AllocationResult` models with upgraded schema attributes, automatic timestamps (`TimestampMixin`), and SQL synonyms.
  - [`app/modules/optimization/schemas.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/optimization/schemas.py): Defined Pydantic models for run details and added request fields and custom model validators to resolve aliases.
  - [`app/modules/optimization/service.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/optimization/service.py): Rewrote optimization engine orchestration with validation summary integration, eligibility filtering rules, and persistence mapping.
  - [`app/modules/optimization/router.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/optimization/router.py): Set route response of the execution endpoint to `OptimizationRunResponse`.
  - [`app/modules/optimization/solver.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/optimization/solver.py): Populated source mapping ID fields on resulting allocation variables.
  - [`app/modules/recommendations/service.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/recommendations/service.py): Supported both uppercase and lowercase status codes in recommendations engine filter logic.
  - [`tests/test_optimization.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/tests/test_optimization.py): Extended tests to run 12 business validations (e.g. demand formula checks, override rules, capacity checks, and invalid exclusions).

---

## 2. Optimizer Input Rules

Before solving, the service integrates the Validation Summary logic:
- If a `CRITICAL` issue is found in the system, no allocations are processed. The run status is saved as `INCOMPLETE`.
- Only records that are `APPROVED`, `is_active = True`, not marked `needs_review`, and within validity dates at `as_of_date` are selected for solver inputs.
- Variable Cost is used only for context/reporting and is **never** used as the objective cost in optimization.

---

## 3. Formulas and Rules

### Demand Formula
For each active eligible plant:
$$\text{monthly\_demand\_mt} = \max(0.0, 30 \times \text{daily\_consumption\_mt} - \text{closing\_stock\_mt})$$

### Capacity Formula
For each eligible `FSA` / `BRIDGE_LINKAGE` constraint:
- If `monthly_cap_mt` is configured:
  $$\text{available\_monthly\_quantity\_mt} = \text{monthly\_cap\_mt}$$
- Otherwise:
  $$\text{available\_monthly\_quantity\_mt} = \frac{\text{annual\_contract\_quantity\_mt} \times 30}{365}$$

### Market Top-up Rule
To guarantee model feasibility, a virtual market top-up allocation is made available per plant:
$$\text{market\_topup\_cost\_per\_mt} = \max(\text{eligible landed costs for plant}) \times 1.20$$
If no active eligible landed cost is resolved and no config fallback exists, the run is flagged as `INCOMPLETE` with a validation issue.

---

## 4. API List

- **POST** `/api/v1/optimization/run`
  - Performs validation pre-checks and executes the allocation engine.
- **GET** `/api/v1/optimization/runs`
  - Returns paginated list of historic runs.
- **GET** `/api/v1/optimization/latest`
  - Returns the latest run detail.
- **GET** `/api/v1/optimization/runs/{run_id}/allocations`
  - Returns the detailed allocation lines of a specific run.

---

## 5. Sample API Responses

### Completed Run Response
```json
{
  "run_id": "c1fba0d8-3111-4140-adda-b8b4b20bdeee",
  "status": "COMPLETED",
  "solver_status": "optimal",
  "total_estimated_cost_rs": 3250000.00,
  "allocation_count": 2,
  "market_topup_required": false,
  "validation_issues": [],
  "message": "Optimization completed successfully."
}
```

### Incomplete Run Response
```json
{
  "run_id": "7a350b9a-1b3e-4988-8c3b-d7c7ba5920e8",
  "status": "INCOMPLETE",
  "solver_status": "validation_failed",
  "total_estimated_cost_rs": null,
  "allocation_count": 0,
  "market_topup_required": false,
  "validation_issues": [
    {
      "code": "MISSING_DAILY_STOCK",
      "severity": "CRITICAL",
      "entity_type": "daily_stock",
      "entity_id": null,
      "plant_id": "337990e2-1b7b-45e9-b807-15958522cc38",
      "message": "No daily stock record has ever been submitted for plant 'ANPARA-A'.",
      "suggested_action": "Upload or enter a daily stock record for this plant."
    }
  ],
  "message": "Input validation failed; required operational data is missing."
}
```

---

## 6. Swagger Verification Steps

1. Launch server: `uvicorn app.main:app --reload`
2. Open OpenAPI UI: `http://localhost:8000/docs`
3. Trigger run execution: `POST /api/v1/optimization/run`
4. Confirm response attributes, error validations, and output structure.

---

## 7. Test Results

All 45 test cases pass successfully:
```
tests\test_daily_stock.py .....                                          [ 11%]
tests\test_fsa_bridge_constraints.py .....                               [ 22%]
tests\test_fsa_constraints.py ..                                         [ 26%]
tests\test_landed_cost.py ...                                            [ 33%]
tests\test_landed_costs_extraction.py ..                                 [ 37%]
tests\test_master_data.py ....                                           [ 46%]
tests\test_optimization.py .........                                     [ 66%]
tests\test_validation_summary.py .....                                   [ 77%]
tests\test_variable_cost_parser.py ........                              [ 95%]
tests\test_variable_cost_upload.py ..                                    [100%]

============================= 45 passed in 2.72s ==============================
```
