from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.modules.audit.models import AuditLog
from app.modules.scheduler.jobs import get_scheduler
from app.modules.scheduler.monitor_models import UpsldcMonitoredReport
from app.modules.scheduler.schemas import (
    DetectedReportItem,
    LastSchedulerEvent,
    SchedulerJobStatus,
    SchedulerStatus,
    UpsldcMonitorStatus,
)

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])
settings = get_settings()


@router.get("/status", response_model=SchedulerStatus)
def get_scheduler_status(db: Session = Depends(get_db)):
    """Fetch read-only operational information of the background scheduler."""
    scheduler = get_scheduler()
    scheduler_running = scheduler is not None and scheduler.running

    registered_jobs = []
    if scheduler:
        for job in scheduler.get_jobs():
            registered_jobs.append(
                SchedulerJobStatus(
                    job_id=job.id,
                    job_name=job.name,
                    trigger=str(job.trigger),
                    next_run_time=job.next_run_time,
                )
            )

    # Last known scheduler audit event (any job)
    last_event = None
    stmt = (
        select(AuditLog)
        .where(AuditLog.source == "SCHEDULER")
        .order_by(AuditLog.occurred_at.desc())
        .limit(1)
    )
    db_event = db.execute(stmt).scalars().first()
    if db_event:
        last_event = LastSchedulerEvent(
            action=db_event.action,
            occurred_at=db_event.occurred_at,
            metadata=db_event.audit_metadata,
        )

    # -----------------------------------------------------------------
    # UPSLDC Monitor status block
    # -----------------------------------------------------------------
    monitor_status = _build_upsldc_monitor_status(db)

    return SchedulerStatus(
        scheduler_enabled=settings.scheduler_enabled,
        scheduler_timezone=settings.scheduler_timezone,
        scheduler_running=scheduler_running,
        registered_jobs=registered_jobs,
        last_event=last_event,
        upsldc_monitor=monitor_status,
    )


def _build_upsldc_monitor_status(db: Session) -> UpsldcMonitorStatus:
    """Build the UPSLDC monitor status sub-object from DB state. Pure read — no side effects."""
    configured_schedule = (
        f"days={settings.upsldc_monitor_schedule_days} "
        f"{settings.upsldc_monitor_hour:02d}:{settings.upsldc_monitor_minute:02d} "
        f"{settings.scheduler_timezone}"
    )

    # Last monitor completion or failure event
    stmt_event = (
        select(AuditLog)
        .where(
            AuditLog.source == "SCHEDULER",
            AuditLog.action.in_(["UPSLDC_MONITOR_COMPLETED", "UPSLDC_MONITOR_FAILED"]),
        )
        .order_by(AuditLog.occurred_at.desc())
        .limit(1)
    )
    last_run_event = db.execute(stmt_event).scalars().first()

    last_monitor_run_at = None
    last_monitor_status = None
    latest_new = None
    latest_existing = None
    last_error: str | None = None

    if last_run_event:
        last_monitor_run_at = last_run_event.occurred_at
        if last_run_event.action == "UPSLDC_MONITOR_COMPLETED":
            last_monitor_status = "COMPLETED"
            meta = last_run_event.audit_metadata or {}
            latest_new = meta.get("new_report_count")
            latest_existing = meta.get("existing_report_count")
        else:
            last_monitor_status = "FAILED"
            meta = last_run_event.audit_metadata or {}
            last_error = meta.get("error")

    # Latest Variable Cost reports seen
    stmt_reports = (
        select(UpsldcMonitoredReport)
        .where(UpsldcMonitoredReport.report_type == "VARIABLE_COST")
        .order_by(UpsldcMonitoredReport.last_seen_at.desc())
        .limit(settings.upsldc_monitor_top_n)
    )
    db_reports = db.execute(stmt_reports).scalars().all()

    detected_items = [
        DetectedReportItem(
            title=r.report_title,
            report_url=r.report_url,
            effective_from=r.effective_from,
            effective_to=r.effective_to,
            first_seen_at=r.first_seen_at,
            last_seen_at=r.last_seen_at,
            detection_status="NEW_DETECTED" if r.first_seen_at == r.last_seen_at else "EXISTING_SEEN",
        )
        for r in db_reports
    ]

    return UpsldcMonitorStatus(
        monitor_enabled=settings.upsldc_monitor_enabled,
        source_name="UPSLDC_SCHMOD",
        source_page_url=settings.upsldc_mod_reports_url,
        top_n=settings.upsldc_monitor_top_n,
        configured_schedule=configured_schedule,
        last_monitor_run_at=last_monitor_run_at,
        last_monitor_status=last_monitor_status,
        latest_detected_variable_cost_reports=detected_items,
        latest_new_report_count=latest_new,
        latest_existing_report_count=latest_existing,
        last_error_safe_message=last_error,
    )
