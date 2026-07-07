from unittest.mock import patch

from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.scheduler.jobs import _heartbeat_job, get_scheduler, shutdown_scheduler, start_scheduler


def test_scheduler_disabled_by_default(client):
    # 1. Scheduler stays disabled when SCHEDULER_ENABLED=false
    # 2. Scheduler does not start during test imports/startup by default
    # 3. Scheduler status endpoint returns safe disabled state
    assert get_scheduler() is None

    resp = client.get("/api/v1/scheduler/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scheduler_enabled"] is False
    assert data["scheduler_running"] is False
    assert len(data["registered_jobs"]) == 0
    assert "limitation" in data
    assert "read-only" in data["limitation"]


def test_scheduler_enabled_in_controlled_setup():
    # 4. Scheduler status endpoint returns registered job details when enabled in controlled test setup
    with patch("app.modules.scheduler.jobs.settings.scheduler_enabled", True):
        scheduler = start_scheduler()
        try:
            assert scheduler is not None
            assert scheduler.running

            jobs = scheduler.get_jobs()
            assert len(jobs) == 1
            job = jobs[0]
            assert job.id == "DOCUMENT_MONITORING_HEARTBEAT"
            assert job.name == "DOCUMENT_MONITORING_HEARTBEAT"
        finally:
            shutdown_scheduler()
            assert get_scheduler() is None


def test_heartbeat_job_creates_audit_events(db_session):
    # 5. Placeholder heartbeat job creates SYSTEM/SCHEDULER audit events
    # 6. Scheduler audit metadata excludes secrets and environment values
    with patch("app.modules.scheduler.jobs.SessionLocal", return_value=db_session):
        _heartbeat_job()

    stmt = select(AuditLog).where(AuditLog.source == "SCHEDULER").order_by(AuditLog.occurred_at.desc())
    logs = db_session.execute(stmt).scalars().all()

    assert len(logs) >= 2

    completed_log = logs[0]
    started_log = logs[1]

    assert started_log.action == "SCHEDULER_JOB_STARTED"
    assert started_log.actor_type == "SYSTEM"
    assert started_log.source == "SCHEDULER"
    assert started_log.audit_metadata["job_name"] == "DOCUMENT_MONITORING_HEARTBEAT"

    assert completed_log.action == "SCHEDULER_JOB_COMPLETED"
    assert completed_log.actor_type == "SYSTEM"
    assert completed_log.source == "SCHEDULER"
    assert completed_log.audit_metadata["result"] == "success"

    # Metadata exclusion assertions
    for key in ["secret", "password", "env", "url", "token", "key"]:
        for log in [started_log, completed_log]:
            meta = log.audit_metadata or {}
            for k in meta.keys():
                assert key not in k.lower()


def test_status_endpoint_creates_no_audit_event(client, db_session):
    # 7. Scheduler status endpoint creates no audit event
    audit_count_before = db_session.execute(select(AuditLog)).scalars().all()

    resp = client.get("/api/v1/scheduler/status")
    assert resp.status_code == 200

    audit_count_after = db_session.execute(select(AuditLog)).scalars().all()
    assert len(audit_count_before) == len(audit_count_after)


def test_no_scheduler_mutation_endpoints(client):
    # 8. No scheduler mutation endpoints exist
    r1 = client.post("/api/v1/scheduler/variable-cost/run-now")
    assert r1.status_code in (404, 405)

    r2 = client.post("/api/v1/scheduler/status")
    assert r2.status_code == 405

    r3 = client.put("/api/v1/scheduler/status")
    assert r3.status_code == 405

    r4 = client.delete("/api/v1/scheduler/status")
    assert r4.status_code == 405
