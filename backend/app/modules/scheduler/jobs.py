"""APScheduler wiring for the daily heartbeats and UPSLDC monitor job.

Only starts a background scheduler when SCHEDULER_ENABLED=true. Timezone matches
Asia/Kolkata by default. The UPSLDC monitor job is registered additionally
only when UPSLDC_MONITOR_ENABLED=true.
"""

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.audit import service as audit_service

logger = logging.getLogger("codsp.scheduler")
settings = get_settings()

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler | None:
    """Return the currently active background scheduler instance."""
    global _scheduler
    return _scheduler


# ---------------------------------------------------------------------------
# Heartbeat job
# ---------------------------------------------------------------------------

def _heartbeat_job() -> None:
    db = SessionLocal()
    run_time = datetime.now(UTC).isoformat()
    try:
        # Record SCHEDULER_JOB_STARTED event
        audit_service.record(
            db,
            entity_type="scheduler",
            entity_id=None,
            action="SCHEDULER_JOB_STARTED",
            actor_type="SYSTEM",
            source="SCHEDULER",
            audit_metadata={
                "job_name": "DOCUMENT_MONITORING_HEARTBEAT",
                "scheduler_timezone": settings.scheduler_timezone,
                "scheduled_run_time": run_time,
            },
        )
        db.commit()

        # Record SCHEDULER_JOB_COMPLETED event
        audit_service.record(
            db,
            entity_type="scheduler",
            entity_id=None,
            action="SCHEDULER_JOB_COMPLETED",
            actor_type="SYSTEM",
            source="SCHEDULER",
            audit_metadata={
                "job_name": "DOCUMENT_MONITORING_HEARTBEAT",
                "scheduler_timezone": settings.scheduler_timezone,
                "scheduled_run_time": run_time,
                "result": "success",
            },
        )
        db.commit()
        logger.info("DOCUMENT_MONITORING_HEARTBEAT executed successfully and recorded audit events.")
    except Exception:
        logger.exception("DOCUMENT_MONITORING_HEARTBEAT job failed.")
        try:
            audit_service.record(
                db,
                entity_type="scheduler",
                entity_id=None,
                action="SCHEDULER_JOB_FAILED",
                actor_type="SYSTEM",
                source="SCHEDULER",
                audit_metadata={
                    "job_name": "DOCUMENT_MONITORING_HEARTBEAT",
                    "scheduler_timezone": settings.scheduler_timezone,
                    "result": "failed",
                },
            )
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ---------------------------------------------------------------------------
# UPSLDC MOD Reports monitor job
# ---------------------------------------------------------------------------

def _upsldc_monitor_job() -> None:
    """Runs the UPSLDC MOD Reports monitor — metadata-only, no PDF downloads."""
    from app.modules.scheduler.upsldc_monitor_service import run_monitor

    db = SessionLocal()
    try:
        audit_service.record(
            db,
            entity_type="scheduler",
            entity_id=None,
            action="SCHEDULER_JOB_STARTED",
            actor_type="SYSTEM",
            source="SCHEDULER",
            audit_metadata={
                "job_name": "UPSLDC_VARIABLE_COST_MONITOR",
                "scheduler_timezone": settings.scheduler_timezone,
            },
        )
        db.commit()

        result = run_monitor(db)

        audit_service.record(
            db,
            entity_type="scheduler",
            entity_id=None,
            action="SCHEDULER_JOB_COMPLETED",
            actor_type="SYSTEM",
            source="SCHEDULER",
            audit_metadata={
                "job_name": "UPSLDC_VARIABLE_COST_MONITOR",
                "scheduler_timezone": settings.scheduler_timezone,
                "run_id": result.run_id,
                "new_report_count": result.new_report_count,
                "existing_report_count": result.existing_report_count,
                "result": "success",
            },
        )
        db.commit()
        logger.info(
            "UPSLDC_VARIABLE_COST_MONITOR completed. new=%d existing=%d",
            result.new_report_count,
            result.existing_report_count,
        )
    except Exception:
        logger.exception("UPSLDC_VARIABLE_COST_MONITOR job failed unexpectedly.")
        try:
            audit_service.record(
                db,
                entity_type="scheduler",
                entity_id=None,
                action="SCHEDULER_JOB_FAILED",
                actor_type="SYSTEM",
                source="SCHEDULER",
                audit_metadata={
                    "job_name": "UPSLDC_VARIABLE_COST_MONITOR",
                    "result": "failed",
                },
            )
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler

    # Scheduler enablement must be explicit through environment configuration
    if not settings.scheduler_enabled:
        logger.info(
            "Scheduler disabled (SCHEDULER_ENABLED=false); background jobs will not run automatically."
        )
        return None

    # Avoid duplicate startup across lifespan cycle reloads
    if _scheduler is not None:
        logger.info("Scheduler already active, skipping start.")
        return _scheduler

    try:
        scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)

        # Always register the heartbeat job
        scheduler.add_job(
            _heartbeat_job,
            trigger=CronTrigger(
                hour=settings.scheduler_document_check_hour,
                minute=settings.scheduler_document_check_minute,
                timezone=settings.scheduler_timezone,
            ),
            id="DOCUMENT_MONITORING_HEARTBEAT",
            name="DOCUMENT_MONITORING_HEARTBEAT",
            replace_existing=True,
        )

        # Conditionally register the UPSLDC monitor job
        if settings.upsldc_monitor_enabled:
            # Parse comma-separated day-of-month list
            schedule_days = settings.upsldc_monitor_schedule_days.strip()
            scheduler.add_job(
                _upsldc_monitor_job,
                trigger=CronTrigger(
                    day=schedule_days,
                    hour=settings.upsldc_monitor_hour,
                    minute=settings.upsldc_monitor_minute,
                    timezone=settings.scheduler_timezone,
                ),
                id="UPSLDC_VARIABLE_COST_MONITOR",
                name="UPSLDC_VARIABLE_COST_MONITOR",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            logger.info(
                "UPSLDC_VARIABLE_COST_MONITOR registered: days=%s %02d:%02d %s",
                schedule_days,
                settings.upsldc_monitor_hour,
                settings.upsldc_monitor_minute,
                settings.scheduler_timezone,
            )

        scheduler.start()
        _scheduler = scheduler
        logger.info(
            "Scheduler started successfully with timezone %s.",
            settings.scheduler_timezone,
        )
        return scheduler
    except Exception as exc:
        logger.exception("Scheduler startup failed.")
        raise exc


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            logger.exception("Error while shutting down scheduler.")
        finally:
            _scheduler = None
