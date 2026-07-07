# Validation Summary API Report

This report outlines the implementation details for the read-only operational data readiness validation summary API.

## 1. Files Changed & Added

- **Added**:
  - [`tests/test_validation_summary.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/tests/test_validation_summary.py): Comprehensive test suite covering critical and warning validation cases.

- **Modified**:
  - [`app/modules/validation/schemas.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/validation/schemas.py): Updated `ValidationIssue` and `ValidationSummary` Pydantic schemas to match structural output specifications.
  - [`app/modules/validation/service.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/validation/service.py): Rewrote summary generation service to check active plants for missing stock, reconciliation errors, missing/unreviewed variable costs, expired/pending constraints, unmapped constraints, pending/rejected/missing landed costs, and document manual review states.

---

## 2. Checks Implemented

### Daily Stock Checks
- `MISSING_DAILY_STOCK` (CRITICAL): Triggered when an active plant has no daily stock record.
- `RECONCILIATION_WARNING` (WARNING): Triggered if a daily stock record's validation status is `"warning"`.

### Variable Cost Checks
- `MISSING_VARIABLE_COST` (CRITICAL): Triggered when an active plant has no approved Variable Cost record.
- `VARIABLE_COST_NEEDS_REVIEW` (WARNING): Triggered if a Variable Cost row has `needs_review = True`.

### FSA / Bridge Constraints Checks
- `UNMAPPED_FSA_BRIDGE_CONSTRAINT` (CRITICAL): Triggered when a constraint has `plant_id is null`.
- `MISSING_ACTIVE_FSA_BRIDGE_CONSTRAINT` (CRITICAL): Triggered when an active plant has no active, approved, non-expired constraints.
- `FSA_BRIDGE_PENDING_REVIEW` (WARNING): Triggered if a constraint's status is `"PENDING_REVIEW"`.
- `REJECTED_FSA_BRIDGE_CONSTRAINT` (WARNING): Triggered if a constraint's status is `"REJECTED"`.
- `EXPIRED_BRIDGE_LINKAGE` (WARNING): Triggered if an approved `BRIDGE_LINKAGE` constraint has expired (`valid_to < today`).

### Landed Cost Checks
- `MISSING_APPROVED_ACTIVE_LANDED_COST` (CRITICAL): Triggered when an active plant has no approved, active, non-expired landed cost record.
- `LANDED_COST_PENDING_REVIEW` (WARNING): Triggered if a landed cost record's status is `"PENDING_REVIEW"`.
- `LANDED_COST_NEEDS_REVIEW` (WARNING): Triggered if a landed cost record has `needs_review = True`.
- `REJECTED_LANDED_COST` (WARNING): Triggered if a landed cost record's status is `"REJECTED"`.

### Documents Checks
- `DOCUMENT_NEEDS_REVIEW` (WARNING): Triggered if a document has `needs_review = True`.

---

## 3. API Response Example

Here is an example response returned by calling `GET /api/v1/validation/summary`:

```json
{
  "overall_status": "INCOMPLETE",
  "generated_at": "2026-07-06T09:21:40.123456Z",
  "as_of_date": "2026-07-06",
  "total_issues": 3,
  "issues": [
    {
      "code": "MISSING_DAILY_STOCK",
      "severity": "CRITICAL",
      "entity_type": "daily_stock",
      "entity_id": null,
      "plant_id": "c1fba0d8-3111-4140-adda-b8b4b20bdeee",
      "message": "No daily stock record has ever been submitted for plant 'VAL01'.",
      "suggested_action": "Upload or enter a daily stock record for this plant."
    },
    {
      "code": "FSA_BRIDGE_PENDING_REVIEW",
      "severity": "WARNING",
      "entity_type": "fsa_constraint",
      "entity_id": "f8facf9e-9ba5-4a1f-a223-866b4c6e0f71",
      "plant_id": "337990e2-1b7b-45e9-b807-15958522cc38",
      "message": "Constraint for raw source 'Anpara' is pending manual review.",
      "suggested_action": "Review and approve/reject the pending constraint."
    },
    {
      "code": "MISSING_APPROVED_ACTIVE_LANDED_COST",
      "severity": "CRITICAL",
      "entity_type": "landed_cost",
      "entity_id": null,
      "plant_id": "7a350b9a-1b3e-4988-8c3b-d7c7ba5920e8",
      "message": "No approved active Landed Cost record is available for plant 'VAL05'.",
      "suggested_action": "Upload landed cost document or approve a pending landed cost for this plant."
    }
  ]
}
```

---

## 4. Swagger Verification Steps

1. Start application server: `uvicorn app.main:app --reload`
2. Access the OpenAPI page in your browser: `http://localhost:8000/docs`
3. Locate the **Validation** router endpoints grouping.
4. Execute `GET /api/v1/validation/summary`.
5. Observe the aggregated readiness status, counts, codes, severities, and suggested actions.

---

## 5. Test Results

All 40 pytest tests pass successfully:
```
tests\test_daily_stock.py .....                                          [ 12%]
tests\test_fsa_bridge_constraints.py .....                               [ 25%]
tests\test_fsa_constraints.py ..                                         [ 30%]
tests\test_landed_cost.py ...                                            [ 37%]
tests\test_landed_costs_extraction.py ..                                 [ 42%]
tests\test_master_data.py ....                                           [ 52%]
tests\test_optimization.py ....                                          [ 62%]
tests\test_validation_summary.py .....                                   [ 75%]
tests\test_variable_cost_parser.py ........                              [ 95%]
tests\test_variable_cost_upload.py ..                                    [100%]

============================= 40 passed in 3.96s ==============================
```
