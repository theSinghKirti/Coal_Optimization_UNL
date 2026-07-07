import uuid
from datetime import date

from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.constraints.models import FSAConstraint
from app.modules.documents.models import Document, VariableCost
from app.modules.landed_cost.models import LandedCost
from app.modules.master_data.models import Plant
from tests.test_fsa_bridge_constraints import REAL_PDF_PATH as FSA_BRIDGE_PDF_PATH
from tests.test_variable_cost_upload import _build_pdf_bytes


def _create_plant(client, code="AUDIT_PLANT"):
    resp = client.post("/api/v1/plants", json={"plant_code": code, "plant_name": f"Plant {code}"})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_daily_stock_creates_audit_record(client, db_session):
    plant_id = _create_plant(client, "DS_AUDIT")
    
    # 1. Clear daily stock audit logs if any
    db_session.execute(select(AuditLog).where(AuditLog.entity_type == "daily_stock"))
    db_session.commit()

    resp = client.post(
        "/api/v1/daily-stock",
        json={
            "plant_id": plant_id,
            "report_date": "2026-01-01",
            "opening_stock_mt": 1000,
            "receipt_mt": 100,
            "consumption_mt": 200,
            "closing_stock_mt": 900,
        },
    )
    assert resp.status_code == 201
    record_id = resp.json()["id"]

    stmt = select(AuditLog).where(
        AuditLog.entity_type == "daily_stock",
        AuditLog.entity_id == uuid.UUID(record_id),
        AuditLog.action == "DAILY_STOCK_CREATED"
    )
    logs = list(db_session.execute(stmt).scalars().all())
    assert len(logs) == 1
    log = logs[0]
    assert log.actor_type == "UNAUTHENTICATED_API"
    assert log.source == "API"
    assert log.after["plant_id"] == plant_id
    assert log.after["opening_stock_mt"] == 1000.0


def test_document_upload_creates_audit_record(client, db_session):
    # Upload clean text PDF
    pdf_bytes = _build_pdf_bytes("Anpara Thermal Power Station 2.40")
    resp = client.post(
        "/api/v1/documents",
        data={"document_type": "FSA_BRIDGE_LINKAGE_DOCUMENT", "original_filename": "fsa.pdf"},
        files={"file": ("fsa.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    stmt = select(AuditLog).where(
        AuditLog.entity_type == "document",
        AuditLog.entity_id == uuid.UUID(doc_id),
        AuditLog.action == "DOCUMENT_UPLOADED"
    )
    logs = list(db_session.execute(stmt).scalars().all())
    assert len(logs) == 1
    log = logs[0]
    assert log.document_id == uuid.UUID(doc_id)
    assert log.actor_type == "UNAUTHENTICATED_API"
    assert log.source == "API"


def test_fsa_extraction_completed_and_failed_audits(client, db_session):
    # Upload FSA Bridge Linkage PDF
    with open(FSA_BRIDGE_PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    resp_upload = client.post(
        "/api/v1/documents",
        data={"document_type": "FSA_BRIDGE_LINKAGE_DOCUMENT", "original_filename": "fsa_real.pdf"},
        files={"file": ("fsa_real.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp_upload.status_code == 201
    doc_id = resp_upload.json()["id"]

    # Clear previous extraction logs for this doc
    db_session.execute(select(AuditLog).where(AuditLog.document_id == uuid.UUID(doc_id)))
    db_session.commit()

    # Trigger extraction (completes successfully)
    resp_extract = client.post(f"/api/v1/documents/{doc_id}/extract")
    assert resp_extract.status_code == 201

    # Expect: DOCUMENT_EXTRACTION_STARTED and DOCUMENT_EXTRACTION_COMPLETED
    stmt = (
        select(AuditLog)
        .where(AuditLog.document_id == uuid.UUID(doc_id))
        .order_by(AuditLog.occurred_at.asc())
    )
    logs = list(db_session.execute(stmt).scalars().all())
    assert any(log.action == "DOCUMENT_EXTRACTION_STARTED" for log in logs)
    assert any(log.action == "DOCUMENT_EXTRACTION_COMPLETED" for log in logs)

    # Let's trigger extraction failure by using a corrupt document path or non-existent file
    # We can create a mock document directly in the database with an invalid storage path
    bad_doc = Document(
        document_type="FSA_BRIDGE_LINKAGE_DOCUMENT",
        original_filename="bad.pdf",
        storage_path="nonexistent_file_path_123.pdf",
        sha256_hash="bad_hash_123"
    )
    db_session.add(bad_doc)
    db_session.commit()

    resp_extract_fail = client.post(f"/api/v1/documents/{bad_doc.id}/extract")
    assert resp_extract_fail.status_code == 422

    # Expect: DOCUMENT_EXTRACTION_FAILED
    stmt_fail = select(AuditLog).where(
        AuditLog.document_id == bad_doc.id,
        AuditLog.action == "DOCUMENT_EXTRACTION_FAILED"
    )
    fail_logs = list(db_session.execute(stmt_fail).scalars().all())
    assert len(fail_logs) == 1
    assert "error" in fail_logs[0].after or "notes" in fail_logs[0].after


def test_fsa_approval_rejection_and_mapping_change_audits(client, db_session):
    plant_a = Plant(plant_code="ANPARA-A-AUDIT", plant_name="Anpara-A Station")
    plant_b = Plant(plant_code="ANPARA-B-AUDIT", plant_name="Anpara-B Station")
    db_session.add_all([plant_a, plant_b])
    db_session.commit()

    doc = Document(
        document_type="FSA_BRIDGE_LINKAGE_DOCUMENT",
        original_filename="dummy.pdf",
        storage_path="dummy",
        sha256_hash="dummy_hash_fsa"
    )
    db_session.add(doc)
    db_session.commit()

    constraint = FSAConstraint(
        constraint_type="FSA",
        plant_id=plant_a.id,
        document_id=doc.id,
        quantity_mt=1000.0,
        status="PENDING_REVIEW"
    )
    db_session.add(constraint)
    db_session.commit()

    # 1. Approve FSA Constraint (also shifts plant mapping from A to B)
    resp_approve = client.post(
        f"/api/v1/fsa-constraints/{constraint.id}/review",
        json={
            "status": "APPROVED",
            "plant_id": str(plant_b.id)
        }
    )
    assert resp_approve.status_code == 200

    # Expect: FSA_CONSTRAINT_APPROVED and FSA_CONSTRAINT_MAPPING_CHANGED
    stmt_app = select(AuditLog).where(
        AuditLog.entity_id == constraint.id
    ).order_by(AuditLog.occurred_at.asc())
    logs = list(db_session.execute(stmt_app).scalars().all())
    
    assert any(log.action == "FSA_CONSTRAINT_MAPPING_CHANGED" for log in logs)
    assert any(log.action == "FSA_CONSTRAINT_APPROVED" for log in logs)

    # Check mapping change before/after state
    map_log = next(log for log in logs if log.action == "FSA_CONSTRAINT_MAPPING_CHANGED")
    assert map_log.before["plant_id"] == str(plant_a.id)
    assert map_log.after["plant_id"] == str(plant_b.id)

    # 2. Reject FSA Constraint
    constraint.status = "PENDING_REVIEW"
    db_session.commit()

    resp_reject = client.post(
        f"/api/v1/fsa-constraints/{constraint.id}/review",
        json={
            "status": "REJECTED"
        }
    )
    assert resp_reject.status_code == 200

    stmt_rej = select(AuditLog).where(
        AuditLog.entity_id == constraint.id,
        AuditLog.action == "FSA_CONSTRAINT_REJECTED"
    )
    assert len(list(db_session.execute(stmt_rej).scalars().all())) == 1


def test_landed_cost_approval_rejection_audits(client, db_session):
    plant = Plant(plant_code="LC-PLANT", plant_name="LC Plant")
    db_session.add(plant)
    db_session.commit()

    doc = Document(
        document_type="LANDED_COST_DOCUMENT",
        original_filename="dummy.pdf",
        storage_path="dummy",
        sha256_hash="dummy_hash_lc"
    )
    db_session.add(doc)
    db_session.commit()

    lc = LandedCost(
        plant_id=plant.id,
        document_id=doc.id,
        total_landed_cost=3000.0,
        status="PENDING_REVIEW",
        needs_review=True,
        effective_from=date(2026, 1, 1)
    )
    db_session.add(lc)
    db_session.commit()

    # Approve Landed Cost
    resp_approve = client.post(
        f"/api/v1/landed-costs/{lc.id}/review",
        json={
            "status": "APPROVED",
            "plant_id": str(plant.id)
        }
    )
    assert resp_approve.status_code == 200

    stmt_app = select(AuditLog).where(
        AuditLog.entity_id == lc.id,
        AuditLog.action == "LANDED_COST_APPROVED"
    )
    assert len(list(db_session.execute(stmt_app).scalars().all())) == 1

    # Reject Landed Cost
    lc.status = "PENDING_REVIEW"
    db_session.commit()

    resp_reject = client.post(
        f"/api/v1/landed-costs/{lc.id}/review",
        json={
            "status": "REJECTED"
        }
    )
    assert resp_reject.status_code == 200

    stmt_rej = select(AuditLog).where(
        AuditLog.entity_id == lc.id,
        AuditLog.action == "LANDED_COST_REJECTED"
    )
    assert len(list(db_session.execute(stmt_rej).scalars().all())) == 1


def test_variable_cost_review_audits(client, db_session):
    plant = Plant(plant_code="VC-PLANT", plant_name="VC Plant")
    db_session.add(plant)
    db_session.commit()

    doc = Document(
        document_type="VARIABLE_COST_PDF",
        original_filename="dummy.pdf",
        storage_path="dummy",
        sha256_hash="dummy_hash_vc"
    )
    db_session.add(doc)
    db_session.commit()

    vc = VariableCost(
        plant_id=None,
        document_id=doc.id,
        source_plant_name="Unresolved VC Plant",
        variable_cost_per_unit=2.15,
        needs_review=True
    )
    db_session.add(vc)
    db_session.commit()

    # Review/approve Variable Cost
    resp = client.patch(
        f"/api/v1/variable-cost/{vc.id}/review",
        json={
            "plant_id": str(plant.id),
            "needs_review": False
        }
    )
    assert resp.status_code == 200

    stmt = select(AuditLog).where(
        AuditLog.entity_id == vc.id,
        AuditLog.action == "VARIABLE_COST_APPROVED"
    )
    logs = list(db_session.execute(stmt).scalars().all())
    assert len(logs) == 1
    assert logs[0].document_id == doc.id


def test_optimization_run_state_audits(client, db_session):
    # Create active plant but no stock data to ensure validation fails (INCOMPLETE)
    plant_id = _create_plant(client, "OPT_INCOMPLETE")

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]

    # Expect: OPTIMIZATION_RUN_REQUESTED and OPTIMIZATION_RUN_INCOMPLETE
    stmt = select(AuditLog).where(
        AuditLog.optimization_run_id == uuid.UUID(run_id)
    ).order_by(AuditLog.occurred_at.asc())
    logs = list(db_session.execute(stmt).scalars().all())
    assert len(logs) == 2
    assert logs[0].action == "OPTIMIZATION_RUN_REQUESTED"
    assert logs[1].action == "OPTIMIZATION_RUN_INCOMPLETE"


def test_optimization_completed_run(client, db_session):
    from tests.test_optimization import _setup_plant_with_stock
    plant_id = _setup_plant_with_stock(client, "OPT_COMP", closing_stock=500, consumption=100)

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
        sha256_hash="hash_opt_comp"
    )
    db_session.add(doc)
    db_session.commit()
    
    vc = VariableCost(
        plant_id=uuid.UUID(plant_id),
        document_id=doc.id,
        source_plant_name="OPT_COMP",
        variable_cost_per_unit=1.5,
        needs_review=False
    )
    db_session.add(vc)
    db_session.commit()

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    run_id = resp.json()["run_id"]

    stmt = select(AuditLog).where(
        AuditLog.optimization_run_id == uuid.UUID(run_id)
    ).order_by(AuditLog.occurred_at.asc())
    logs = list(db_session.execute(stmt).scalars().all())
    assert len(logs) == 2
    assert logs[0].action == "OPTIMIZATION_RUN_REQUESTED"
    assert logs[1].action == "OPTIMIZATION_RUN_COMPLETED"


def test_audit_snapshots_do_not_contain_secrets(client, db_session):
    stmt = select(AuditLog).limit(10)
    logs = list(db_session.execute(stmt).scalars().all())
    
    disallowed_substrings = ["pdf_text", "password", "jwt", "secret", "file_bytes"]
    for log in logs:
        for val in (log.before, log.after, log.audit_metadata):
            if val:
                val_str = str(val).lower()
                for sub in disallowed_substrings:
                    assert sub not in val_str


def test_list_audit_logs_filters_pagination_and_mutations(client, db_session):
    from datetime import datetime

    from app.modules.audit.service import record as audit_record
    from app.modules.optimization.models import OptimizationRun
    
    # Clean previous audit logs for this specific test block
    db_session.query(AuditLog).delete()
    db_session.commit()

    # Seed a dummy Document and OptimizationRun to prevent foreign key violations
    doc = Document(
        document_type="VARIABLE_COST_PDF",
        original_filename="dummy.pdf",
        storage_path="dummy",
        sha256_hash="dummy_hash_test_audit"
    )
    db_session.add(doc)
    db_session.flush()

    run = OptimizationRun(
        run_timestamp=datetime.utcnow(),
        status="COMPLETED",
        solver_status="optimal",
        total_estimated_cost=1000.0,
    )
    db_session.add(run)
    db_session.flush()

    from datetime import timedelta
    now_time = datetime.utcnow()

    log1 = audit_record(
        db_session,
        entity_type="daily_stock",
        entity_id=uuid.uuid4(),
        action="TEST_ACTION_A",
        before={"status": "old", "password": "secret_password"},
        after={"status": "new", "jwt_token": "secret_jwt"},
        occurred_at=now_time - timedelta(seconds=10),
    )
    log2 = audit_record(
        db_session,
        entity_type="document",
        entity_id=uuid.uuid4(),
        action="TEST_ACTION_B",
        document_id=doc.id,
        occurred_at=now_time - timedelta(seconds=5),
    )
    log3 = audit_record(
        db_session,
        entity_type="optimization_run",
        entity_id=uuid.uuid4(),
        action="TEST_ACTION_C",
        optimization_run_id=run.id,
        occurred_at=now_time,
    )
    db_session.commit()

    # 1. List endpoint returns audit records newest first
    resp = client.get("/api/v1/audit-logs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    items = data["items"]
    assert items[0]["action"] == "TEST_ACTION_C"
    assert items[1]["action"] == "TEST_ACTION_B"
    assert items[2]["action"] == "TEST_ACTION_A"

    # 2. Pagination works correctly
    resp_pag = client.get("/api/v1/audit-logs?page=1&page_size=2")
    assert resp_pag.status_code == 200
    data_pag = resp_pag.json()
    assert len(data_pag["items"]) == 2
    assert data_pag["has_next_page"] is True

    # 3. page_size above maximum is rejected
    resp_bad_size = client.get("/api/v1/audit-logs?page_size=101")
    assert resp_bad_size.status_code == 422

    # 4. Filter by action works
    resp_filter_act = client.get("/api/v1/audit-logs?action=TEST_ACTION_B")
    assert resp_filter_act.status_code == 200
    assert resp_filter_act.json()["total"] == 1
    assert resp_filter_act.json()["items"][0]["action"] == "TEST_ACTION_B"

    # 5. Filter by entity_type works
    resp_filter_type = client.get("/api/v1/audit-logs?entity_type=optimization_run")
    assert resp_filter_type.status_code == 200
    assert resp_filter_type.json()["total"] == 1
    assert resp_filter_type.json()["items"][0]["entity_type"] == "optimization_run"

    # 6. Filter by entity_id works
    resp_filter_ent_id = client.get(f"/api/v1/audit-logs?entity_id={log2.entity_id}")
    assert resp_filter_ent_id.status_code == 200
    assert resp_filter_ent_id.json()["total"] == 1

    # 7. Filter by document_id works
    resp_filter_doc_id = client.get(f"/api/v1/audit-logs?document_id={log2.document_id}")
    assert resp_filter_doc_id.status_code == 200
    assert resp_filter_doc_id.json()["total"] == 1

    # 8. Filter by optimization_run_id works
    resp_filter_run_id = client.get(f"/api/v1/audit-logs?optimization_run_id={log3.optimization_run_id}")
    assert resp_filter_run_id.status_code == 200
    assert resp_filter_run_id.json()["total"] == 1

    # 9. Date-range filter works
    occurred_str = datetime.now().isoformat()
    resp_filter_date = client.get(f"/api/v1/audit-logs?occurred_from={occurred_str}")
    assert resp_filter_date.status_code == 200

    # 10. Empty result returns safe empty list with total = 0
    resp_empty = client.get("/api/v1/audit-logs?action=NON_EXISTENT_ACTION_123")
    assert resp_empty.status_code == 200
    data_empty = resp_empty.json()
    assert data_empty["total"] == 0
    assert data_empty["items"] == []
    assert data_empty["has_next_page"] is False

    # 11. Detail endpoint returns one valid record
    resp_detail = client.get(f"/api/v1/audit-logs/{log1.id}")
    assert resp_detail.status_code == 200
    assert resp_detail.json()["action"] == "TEST_ACTION_A"

    # 12. Unknown audit_log_id returns 404
    resp_detail_missing = client.get(f"/api/v1/audit-logs/{uuid.uuid4()}")
    assert resp_detail_missing.status_code == 404

    # 13. Sensitive keys are removed from API response (redaction checks)
    log1_resp = resp_detail.json()
    before_str = str(log1_resp["before_state"]).lower()
    after_str = str(log1_resp["after_state"]).lower()
    assert "password" not in before_str
    assert "jwt" not in after_str
    assert "secret" not in before_str
    assert "secret" not in after_str

    # 14. POST /api/v1/audit-logs is not available
    resp_post = client.post("/api/v1/audit-logs", json={"action": "TEST"})
    assert resp_post.status_code in (404, 405)

    # 15. PATCH/PUT/DELETE audit-log mutation routes are not available
    resp_patch = client.patch(f"/api/v1/audit-logs/{log1.id}", json={"action": "TEST"})
    assert resp_patch.status_code in (404, 405)
    resp_delete = client.delete(f"/api/v1/audit-logs/{log1.id}")
    assert resp_delete.status_code in (404, 405)
