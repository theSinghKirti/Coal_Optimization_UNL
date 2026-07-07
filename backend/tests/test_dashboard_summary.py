import uuid
from datetime import date

from sqlalchemy import select

from app.modules.constraints.models import FSAConstraint
from app.modules.documents.models import Document, VariableCost
from app.modules.landed_cost.models import LandedCost


def _create_plant(client, code="PL_DASH"):
    resp = client.post("/api/v1/plants", json={"plant_code": code, "plant_name": f"Plant {code}"})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_dashboard_summary_empty_database(client):
    # 1. Summary returns successfully when database has no operational records
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    
    assert "metadata" in data
    assert "validation" in data
    assert "optimization" in data
    assert "coverage" in data
    assert "next_actions" in data

    # 8. Summary returns safe no-run state when optimization run does not exist
    opt = data["optimization"]
    assert opt["latest_run_exists"] is False
    assert opt["run_id"] is None
    assert opt["run_status"] is None
    assert opt["total_demand_mt"] is None


def test_dashboard_summary_validation_and_coverage(client, db_session):
    # 2. Summary correctly reflects existing validation INCOMPLETE state
    # 3. Summary correctly includes current validation issue counts
    # 4. Summary correctly reports missing daily stock coverage
    # 5. Summary correctly reports pending/unmapped FSA / Bridge constraints
    # 6. Summary correctly reports pending/needs-review landed costs
    
    plant_id = _create_plant(client, "VAL_COV_PL")
    
    # Add an unmapped constraint
    c1 = FSAConstraint(
        constraint_type="FSA",
        plant_id=None,
        quantity_mt=1000.0,
        status="PENDING_REVIEW"
    )
    db_session.add(c1)
    
    # Add a pending landed cost
    lc1 = LandedCost(
        plant_id=uuid.UUID(plant_id),
        total_landed_cost=2500.0,
        status="PENDING_REVIEW",
        needs_review=True,
        effective_from=date(2026, 1, 1)
    )
    db_session.add(lc1)
    db_session.commit()

    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    
    # Validation
    val = data["validation"]
    assert val["validation_status"] == "INCOMPLETE"
    assert val["critical_issue_count"] > 0
    assert val["total_issue_count"] > 0
    
    # Limit blockers to 5
    # 10. Top blockers are limited and safely formatted
    assert len(val["top_blockers"]) <= 5
    for blocker in val["top_blockers"]:
        assert "code" in blocker
        assert "severity" in blocker
        assert "message" in blocker

    # Coverage
    cov = data["coverage"]
    assert cov["daily_stock"]["plants_missing_latest_daily_stock"] > 0
    assert cov["fsa_constraint"]["unmapped_constraint_count"] == 1
    assert cov["landed_cost"]["pending_review_landed_cost_count"] == 1
    assert cov["landed_cost"]["needs_review_landed_cost_count"] == 1

    # Next Actions
    # 11. Next required actions are deterministic and based only on backend data
    actions = data["next_actions"]
    assert len(actions) > 0
    modules = [a["related_module"] for a in actions]
    assert "daily_stock" in modules
    assert "fsa_constraint" in modules
    assert "landed_cost" in modules


def test_dashboard_summary_incomplete_run_no_allocation_totals(client, db_session):
    # 7. Summary returns no fake allocation totals for INCOMPLETE run
    plant_id = _create_plant(client, "VAL_INCOMP_PL")
    
    # Request optimization run when data is incomplete -> run is marked INCOMPLETE
    resp_run = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp_run.status_code == 201
    run_id = resp_run.json()["run_id"]

    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    
    opt = data["optimization"]
    assert opt["latest_run_exists"] is True
    assert opt["run_id"] == run_id
    assert opt["run_status"] == "INCOMPLETE"
    
    # Verify metrics are null
    assert opt["plants_covered_count"] is None
    assert opt["total_demand_mt"] is None
    assert opt["total_allocated_mt"] is None
    assert opt["total_estimated_cost"] is None


def test_dashboard_summary_completed_run(client, db_session):
    # 9. Controlled COMPLETED optimization fixture returns real allocation metrics
    from tests.test_optimization import _setup_plant_with_stock
    plant_id = _setup_plant_with_stock(client, "DASH_COMP", closing_stock=500, consumption=100)

    client.post(
        "/api/v1/fsa-constraints",
        json={
            "constraint_type": "FSA",
            "plant_id": plant_id,
            "annual_contract_quantity_mt": 365000,
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2028-12-31",
        },
    )
    client.post(
        "/api/v1/landed-costs",
        json={
            "plant_id": plant_id,
            "basic_cost": 1000,
            "freight": 200,
            "taxes": 100,
            "other_cost": 0,
            "effective_from": "2026-01-01",
        },
    )

    constraint = db_session.execute(
        select(FSAConstraint).where(FSAConstraint.plant_id == uuid.UUID(plant_id))
    ).scalars().first()
    constraint.status = "APPROVED"
    constraint.valid_to = date(2028, 12, 31)
    
    lc = db_session.execute(
        select(LandedCost).where(LandedCost.plant_id == uuid.UUID(plant_id))
    ).scalars().first()
    lc.status = "APPROVED"
    lc.needs_review = False
    
    doc = Document(
        document_type="VARIABLE_COST_PDF",
        original_filename="vc.pdf",
        storage_path="dummy",
        sha256_hash="hash_dash_comp"
    )
    db_session.add(doc)
    db_session.commit()
    
    vc = VariableCost(
        plant_id=uuid.UUID(plant_id),
        document_id=doc.id,
        source_plant_name="DASH_COMP",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    db_session.add(vc)
    db_session.commit()

    resp_run = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp_run.status_code == 201
    run_id = resp_run.json()["run_id"]

    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    
    opt = data["optimization"]
    assert opt["latest_run_exists"] is True
    assert opt["run_id"] == run_id
    assert opt["run_status"] == "COMPLETED"
    
    # Verify allocation metrics are populated and match actual run results
    assert opt["plants_covered_count"] == 1
    assert opt["total_demand_mt"] == 2500.0  # (consumption 100 - closing stock 500)?
    # Wait, in the solver test we verified: total_estimated_cost = 2500.0 * 1300.0, allocated = 2500.0
    assert opt["total_allocated_mt"] == 2500.0
    assert opt["allocation_count"] == 1
    assert opt["total_estimated_cost"] == 2500.0 * 1300.0
