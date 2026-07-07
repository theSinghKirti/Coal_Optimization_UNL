import uuid
from datetime import date

from sqlalchemy import select

from app.modules.constraints.models import FSAConstraint
from app.modules.documents.models import Document, VariableCost
from app.modules.landed_cost.models import LandedCost


def _setup_plant_with_stock(client, code, *, closing_stock, consumption):
    plant = client.post("/api/v1/plants", json={"plant_code": code, "plant_name": f"Plant {code}"}).json()
    client.post(
        "/api/v1/daily-stock",
        json={
            "plant_id": plant["id"],
            "report_date": str(date.today()),
            "opening_stock_mt": closing_stock + consumption,
            "receipt_mt": 0,
            "consumption_mt": consumption,
            "closing_stock_mt": closing_stock,
        },
    )
    return plant["id"]


# --- Legacy Tests Updated for Milestone 7 ---

def test_optimization_allocates_from_fsa_using_landed_cost(client, db_session):
    plant_id = _setup_plant_with_stock(client, "OPT01", closing_stock=500, consumption=100)

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
        sha256_hash="hash_opt01"
    )
    db_session.add(doc)
    db_session.flush()
    
    vc = VariableCost(
        plant_id=uuid.UUID(plant_id),
        document_id=doc.id,
        source_plant_name="OPT01",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    db_session.add(vc)
    db_session.flush()

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["solver_status"] == "optimal"
    assert body["allocation_count"] == 1
    assert body["total_estimated_cost_rs"] == 2500.0 * 1300.0


def test_market_topup_used_when_acq_cap_insufficient(client, db_session):
    plant_id = _setup_plant_with_stock(client, "OPT02", closing_stock=500, consumption=100)

    client.post(
        "/api/v1/fsa-constraints",
        json={
            "constraint_type": "FSA",
            "plant_id": plant_id,
            "annual_contract_quantity_mt": 12000,
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2028-12-31",
        },
    )
    client.post(
        "/api/v1/landed-costs",
        json={
            "plant_id": plant_id,
            "basic_cost": 1000,
            "freight": 0,
            "taxes": 0,
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
        sha256_hash="hash_opt02"
    )
    db_session.add(doc)
    db_session.flush()
    
    vc = VariableCost(
        plant_id=uuid.UUID(plant_id),
        document_id=doc.id,
        source_plant_name="OPT02",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    db_session.add(vc)
    db_session.flush()

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["market_topup_required"] is True


def test_incomplete_data_when_no_landed_cost_and_no_fallback(client, db_session):
    plant_id = _setup_plant_with_stock(client, "OPT03", closing_stock=500, consumption=100)
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

    constraint = db_session.execute(
        select(FSAConstraint).where(FSAConstraint.plant_id == uuid.UUID(plant_id))
    ).scalars().first()
    constraint.status = "APPROVED"
    constraint.valid_to = date(2028, 12, 31)

    doc = Document(
        document_type="VARIABLE_COST_PDF",
        original_filename="vc.pdf",
        storage_path="dummy",
        sha256_hash="hash_opt03"
    )
    db_session.add(doc)
    db_session.flush()
    
    vc = VariableCost(
        plant_id=uuid.UUID(plant_id),
        document_id=doc.id,
        source_plant_name="OPT03",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    db_session.add(vc)
    db_session.flush()

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "INCOMPLETE"


def test_no_shortfall_returns_completed_with_no_allocation(client, db_session):
    plant_id = _setup_plant_with_stock(client, "OPT04", closing_stock=100000, consumption=10)

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
            "freight": 0,
            "taxes": 0,
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
        sha256_hash="hash_opt04"
    )
    db_session.add(doc)
    db_session.flush()
    
    vc = VariableCost(
        plant_id=uuid.UUID(plant_id),
        document_id=doc.id,
        source_plant_name="OPT04",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    db_session.add(vc)
    db_session.flush()

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["allocation_count"] == 0


# --- New Milestone 7 Specific Behavior Tests ---

def test_monthly_demand_calculation(client, db_session):
    plant_id = _setup_plant_with_stock(client, "DEM01", closing_stock=1000, consumption=150)
    
    client.post("/api/v1/fsa-constraints", json={
        "constraint_type": "FSA",
        "plant_id": plant_id,
        "annual_contract_quantity_mt": 365000,
        "contract_start_date": "2026-01-01",
        "contract_end_date": "2028-12-31"
    })
    client.post("/api/v1/landed-costs", json={
        "plant_id": plant_id,
        "basic_cost": 1000,
        "freight": 0,
        "taxes": 0,
        "other_cost": 0,
        "effective_from": "2026-01-01"
    })
    
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
        sha256_hash="hash_dem01"
    )
    db_session.add(doc)
    db_session.flush()
    
    vc = VariableCost(
        plant_id=uuid.UUID(plant_id),
        document_id=doc.id,
        source_plant_name="DEM01",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    db_session.add(vc)
    db_session.flush()

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "COMPLETED"
    
    allocations_resp = client.get(f"/api/v1/optimization/runs/{body['run_id']}/allocations")
    assert allocations_resp.status_code == 200
    allocations = allocations_resp.json()
    total_qty = sum(a["allocated_quantity_mt"] for a in allocations)
    assert total_qty == 3500.0


def test_monthly_acq_cap_calculation_using_annual_quantity(client, db_session):
    plant_id = _setup_plant_with_stock(client, "CAP01", closing_stock=500, consumption=200)
    
    client.post("/api/v1/fsa-constraints", json={
        "constraint_type": "FSA",
        "plant_id": plant_id,
        "annual_contract_quantity_mt": 36500,
        "contract_start_date": "2026-01-01",
        "contract_end_date": "2028-12-31"
    })
    client.post("/api/v1/landed-costs", json={
        "plant_id": plant_id,
        "basic_cost": 1000,
        "freight": 0,
        "taxes": 0,
        "other_cost": 0,
        "effective_from": "2026-01-01"
    })
    
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
        sha256_hash="hash_cap01"
    )
    db_session.add(doc)
    db_session.flush()
    
    vc = VariableCost(
        plant_id=uuid.UUID(plant_id),
        document_id=doc.id,
        source_plant_name="CAP01",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    db_session.add(vc)
    db_session.flush()

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    body = resp.json()
    
    allocations = client.get(f"/api/v1/optimization/runs/{body['run_id']}/allocations").json()
    fsa_qty = sum(a["allocated_quantity_mt"] for a in allocations if a["allocation_type"] == "fsa")
    assert fsa_qty == 3000.0
    topup_qty = sum(a["allocated_quantity_mt"] for a in allocations if a["allocation_type"] == "market_topup")
    assert topup_qty == 2500.0


def test_monthly_cap_override_when_monthly_cap_mt_exists(client, db_session):
    plant_id = _setup_plant_with_stock(client, "CAP02", closing_stock=500, consumption=200)
    
    client.post("/api/v1/fsa-constraints", json={
        "constraint_type": "FSA",
        "plant_id": plant_id,
        "annual_contract_quantity_mt": 36500,
        "monthly_cap_mt": 4000,
        "contract_start_date": "2026-01-01",
        "contract_end_date": "2028-12-31"
    })
    client.post("/api/v1/landed-costs", json={
        "plant_id": plant_id,
        "basic_cost": 1000,
        "freight": 0,
        "taxes": 0,
        "other_cost": 0,
        "effective_from": "2026-01-01"
    })
    
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
        sha256_hash="hash_cap02"
    )
    db_session.add(doc)
    db_session.flush()
    
    vc = VariableCost(
        plant_id=uuid.UUID(plant_id),
        document_id=doc.id,
        source_plant_name="CAP02",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    db_session.add(vc)
    db_session.flush()

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    body = resp.json()
    
    allocations = client.get(f"/api/v1/optimization/runs/{body['run_id']}/allocations").json()
    fsa_qty = sum(a["allocated_quantity_mt"] for a in allocations if a["allocation_type"] == "fsa")
    assert fsa_qty == 4000.0


def test_variable_cost_not_used_as_objective_cost(client, db_session):
    plant_id = _setup_plant_with_stock(client, "VC01", closing_stock=500, consumption=100)
    
    client.post("/api/v1/fsa-constraints", json={
        "constraint_type": "FSA",
        "plant_id": plant_id,
        "annual_contract_quantity_mt": 365000,
        "contract_start_date": "2026-01-01",
        "contract_end_date": "2028-12-31"
    })
    client.post("/api/v1/landed-costs", json={
        "plant_id": plant_id,
        "basic_cost": 1000,
        "freight": 200,
        "taxes": 100,
        "other_cost": 0,
        "effective_from": "2026-01-01"
    })
    
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
        sha256_hash="hash_vc01"
    )
    db_session.add(doc)
    db_session.flush()
    
    vc = VariableCost(
        plant_id=uuid.UUID(plant_id),
        document_id=doc.id,
        source_plant_name="VC01",
        variable_cost_per_unit=5.0,
        needs_review=False
    )
    db_session.add(vc)
    db_session.flush()

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    body = resp.json()
    
    allocations = client.get(f"/api/v1/optimization/runs/{body['run_id']}/allocations").json()
    assert allocations[0]["unit_cost"] == 1300.0


def test_invalid_records_excluded_and_persistence(client, db_session):
    plant_id = _setup_plant_with_stock(client, "EXC01", closing_stock=500, consumption=100)
    
    client.post("/api/v1/fsa-constraints", json={
        "constraint_type": "FSA",
        "plant_id": plant_id,
        "annual_contract_quantity_mt": 365000,
        "contract_start_date": "2026-01-01",
        "contract_end_date": "2028-12-31"
    })
    client.post("/api/v1/landed-costs", json={
        "plant_id": plant_id,
        "basic_cost": 1000,
        "freight": 200,
        "taxes": 100,
        "other_cost": 0,
        "effective_from": "2026-01-01"
    })
    
    c_approved = db_session.execute(
        select(FSAConstraint).where(FSAConstraint.plant_id == uuid.UUID(plant_id))
    ).scalars().first()
    c_approved.status = "APPROVED"
    c_approved.valid_to = date(2028, 12, 31)

    lc_approved = db_session.execute(
        select(LandedCost).where(LandedCost.plant_id == uuid.UUID(plant_id))
    ).scalars().first()
    lc_approved.status = "APPROVED"
    lc_approved.needs_review = False

    c_expired = FSAConstraint(
        plant_id=uuid.UUID(plant_id),
        constraint_type="FSA",
        annual_contract_quantity_mt=50000,
        contract_start_date=date(2020, 1, 1),
        contract_end_date=date(2021, 12, 31),
        status="APPROVED",
        is_active=True,
        valid_to=date(2021, 12, 31)
    )
    c_pending = FSAConstraint(
        plant_id=uuid.UUID(plant_id),
        constraint_type="FSA",
        annual_contract_quantity_mt=50000,
        status="PENDING_REVIEW",
        is_active=True
    )
    c_rejected = FSAConstraint(
        plant_id=uuid.UUID(plant_id),
        constraint_type="FSA",
        annual_contract_quantity_mt=50000,
        status="REJECTED",
        is_active=True
    )
    db_session.add_all([c_expired, c_pending, c_rejected])
    
    doc = Document(
        document_type="VARIABLE_COST_PDF",
        original_filename="vc.pdf",
        storage_path="dummy",
        sha256_hash="hash_exc01"
    )
    db_session.add(doc)
    db_session.flush()
    
    vc = VariableCost(
        plant_id=uuid.UUID(plant_id),
        document_id=doc.id,
        source_plant_name="EXC01",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    db_session.add(vc)
    db_session.flush()

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "COMPLETED"
    
    from app.modules.optimization.models import OptimizationRun
    db_run = db_session.get(OptimizationRun, body["run_id"])
    assert db_run is not None
    assert db_run.status == "COMPLETED"
    assert len(db_run.allocations) == 1
    assert db_run.allocations[0].allocation_type == "fsa"
    assert db_run.allocations[0].fsa_constraint_id == c_approved.id
