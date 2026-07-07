from datetime import date

from app.modules.constraints.models import FSAConstraint
from app.modules.landed_cost.models import LandedCost
from app.modules.master_data.models import Plant


def test_validation_summary_missing_daily_stock_creates_critical(client, db_session):
    p = Plant(plant_code="VAL01", plant_name="Validation Plant 01", is_active=True)
    db_session.add(p)
    db_session.flush()

    resp = client.get("/api/v1/validation/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_status"] == "INCOMPLETE"
    
    issues = [iss for iss in data["issues"] if iss["code"] == "MISSING_DAILY_STOCK"]
    assert len(issues) == 1
    assert issues[0]["severity"] == "CRITICAL"
    assert issues[0]["plant_id"] == str(p.id)


def test_validation_summary_pending_fsa_creates_warning(client, db_session):
    p = Plant(plant_code="VAL02", plant_name="Validation Plant 02", is_active=True)
    db_session.add(p)
    db_session.flush()

    # Create daily stock via API
    resp_ds = client.post(
        "/api/v1/daily-stock",
        json={
            "plant_id": str(p.id),
            "report_date": str(date.today()),
            "opening_stock_mt": 900.0,
            "receipt_mt": 200.0,
            "consumption_mt": 100.0,
            "closing_stock_mt": 1000.0,
        }
    )
    assert resp_ds.status_code == 201

    lc = LandedCost(
        plant_id=p.id,
        total_landed_cost=1000.0,
        effective_from=date.today(),
        is_active=True,
        status="APPROVED"
    )
    from app.modules.documents.models import Document, VariableCost
    doc = Document(
        document_type="VARIABLE_COST_PDF",
        original_filename="vc.pdf",
        storage_path="dummy",
        sha256_hash="hash123"
    )
    db_session.add(doc)
    db_session.flush()

    vc = VariableCost(
        plant_id=p.id,
        document_id=doc.id,
        source_plant_name="VAL02",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    db_session.add_all([lc, vc])
    db_session.flush()

    c_approved = FSAConstraint(
        plant_id=p.id,
        constraint_type="FSA",
        annual_contract_quantity_mt=1000,
        is_active=True,
        status="APPROVED",
        valid_to=date(2028, 12, 31)
    )
    c_pending = FSAConstraint(
        plant_id=p.id,
        constraint_type="FSA",
        annual_contract_quantity_mt=500,
        is_active=False,
        status="PENDING_REVIEW"
    )
    db_session.add_all([c_approved, c_pending])
    db_session.flush()

    resp = client.get("/api/v1/validation/summary")
    assert resp.status_code == 200
    data = resp.json()
    
    assert data["overall_status"] == "WARNING"
    
    issues = [iss for iss in data["issues"] if iss["code"] == "FSA_BRIDGE_PENDING_REVIEW"]
    assert len(issues) == 1
    assert issues[0]["severity"] == "WARNING"


def test_validation_summary_unmapped_fsa_creates_critical(client, db_session):
    p = Plant(plant_code="VAL03", plant_name="Validation Plant 03", is_active=True)
    db_session.add(p)
    db_session.flush()

    # Create daily stock via API
    resp_ds = client.post(
        "/api/v1/daily-stock",
        json={
            "plant_id": str(p.id),
            "report_date": str(date.today()),
            "opening_stock_mt": 900.0,
            "receipt_mt": 200.0,
            "consumption_mt": 100.0,
            "closing_stock_mt": 1000.0,
        }
    )
    assert resp_ds.status_code == 201

    lc = LandedCost(
        plant_id=p.id,
        total_landed_cost=1000.0,
        effective_from=date.today(),
        is_active=True,
        status="APPROVED"
    )
    from app.modules.documents.models import Document, VariableCost
    doc = Document(
        document_type="VARIABLE_COST_PDF",
        original_filename="vc.pdf",
        storage_path="dummy",
        sha256_hash="hash456"
    )
    db_session.add(doc)
    db_session.flush()

    vc = VariableCost(
        plant_id=p.id,
        document_id=doc.id,
        source_plant_name="VAL03",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    c_approved = FSAConstraint(
        plant_id=p.id,
        constraint_type="FSA",
        annual_contract_quantity_mt=1000,
        is_active=True,
        status="APPROVED",
        valid_to=date(2028, 12, 31)
    )
    db_session.add_all([lc, vc, c_approved])
    db_session.flush()

    c_unmapped = FSAConstraint(
        plant_id=None,
        constraint_type="FSA",
        annual_contract_quantity_mt=500,
        is_active=False,
        status="PENDING_REVIEW"
    )
    db_session.add(c_unmapped)
    db_session.flush()

    resp = client.get("/api/v1/validation/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_status"] == "INCOMPLETE"

    issues = [iss for iss in data["issues"] if iss["code"] == "UNMAPPED_FSA_BRIDGE_CONSTRAINT"]
    assert len(issues) == 1
    assert issues[0]["severity"] == "CRITICAL"


def test_validation_summary_pending_landed_cost_creates_warning(client, db_session):
    p = Plant(plant_code="VAL04", plant_name="Validation Plant 04", is_active=True)
    db_session.add(p)
    db_session.flush()

    # Create daily stock via API
    resp_ds = client.post(
        "/api/v1/daily-stock",
        json={
            "plant_id": str(p.id),
            "report_date": str(date.today()),
            "opening_stock_mt": 900.0,
            "receipt_mt": 200.0,
            "consumption_mt": 100.0,
            "closing_stock_mt": 1000.0,
        }
    )
    assert resp_ds.status_code == 201

    lc_approved = LandedCost(
        plant_id=p.id,
        total_landed_cost=1000.0,
        effective_from=date.today(),
        is_active=True,
        status="APPROVED"
    )
    from app.modules.documents.models import Document, VariableCost
    doc = Document(
        document_type="VARIABLE_COST_PDF",
        original_filename="vc.pdf",
        storage_path="dummy",
        sha256_hash="hash789"
    )
    db_session.add(doc)
    db_session.flush()

    vc = VariableCost(
        plant_id=p.id,
        document_id=doc.id,
        source_plant_name="VAL04",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    c_approved = FSAConstraint(
        plant_id=p.id,
        constraint_type="FSA",
        annual_contract_quantity_mt=1000,
        is_active=True,
        status="APPROVED",
        valid_to=date(2028, 12, 31)
    )
    db_session.add_all([lc_approved, vc, c_approved])
    db_session.flush()

    lc_pending = LandedCost(
        plant_id=p.id,
        total_landed_cost=800.0,
        effective_from=date.today(),
        is_active=False,
        status="PENDING_REVIEW"
    )
    db_session.add(lc_pending)
    db_session.flush()

    resp = client.get("/api/v1/validation/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_status"] == "WARNING"

    issues = [iss for iss in data["issues"] if iss["code"] == "LANDED_COST_PENDING_REVIEW"]
    assert len(issues) == 1
    assert issues[0]["severity"] == "WARNING"


def test_validation_summary_missing_approved_land_cost_creates_critical(client, db_session):
    p = Plant(plant_code="VAL05", plant_name="Validation Plant 05", is_active=True)
    db_session.add(p)
    db_session.flush()

    # Create daily stock via API
    resp_ds = client.post(
        "/api/v1/daily-stock",
        json={
            "plant_id": str(p.id),
            "report_date": str(date.today()),
            "opening_stock_mt": 900.0,
            "receipt_mt": 200.0,
            "consumption_mt": 100.0,
            "closing_stock_mt": 1000.0,
        }
    )
    assert resp_ds.status_code == 201

    from app.modules.documents.models import Document, VariableCost
    doc = Document(
        document_type="VARIABLE_COST_PDF",
        original_filename="vc.pdf",
        storage_path="dummy",
        sha256_hash="hashabc"
    )
    db_session.add(doc)
    db_session.flush()

    vc = VariableCost(
        plant_id=p.id,
        document_id=doc.id,
        source_plant_name="VAL05",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    c_approved = FSAConstraint(
        plant_id=p.id,
        constraint_type="FSA",
        annual_contract_quantity_mt=1000,
        is_active=True,
        status="APPROVED",
        valid_to=date(2028, 12, 31)
    )
    db_session.add_all([vc, c_approved])
    db_session.flush()

    resp = client.get("/api/v1/validation/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_status"] == "INCOMPLETE"

    issues = [iss for iss in data["issues"] if iss["code"] == "MISSING_APPROVED_ACTIVE_LANDED_COST"]
    assert len(issues) == 1
    assert issues[0]["severity"] == "CRITICAL"
