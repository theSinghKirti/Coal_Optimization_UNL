from datetime import date, datetime

from pydantic import BaseModel


class IngestionRunResult(BaseModel):
    source_reachable: bool
    discovered_links: int
    downloaded: int
    skipped_duplicates: int
    failed_downloads: int
    documents_created: list[str]
    notes: list[str]


class SchedulerJobStatus(BaseModel):
    job_id: str
    job_name: str
    trigger: str
    next_run_time: datetime | None = None


class LastSchedulerEvent(BaseModel):
    action: str
    occurred_at: datetime
    metadata: dict | None = None


# ---------------------------------------------------------------------------
# UPSLDC Monitor status schemas
# ---------------------------------------------------------------------------


class DetectedReportItem(BaseModel):
    title: str
    report_url: str
    effective_from: date | None = None
    effective_to: date | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    detection_status: str  # NEW_DETECTED | EXISTING_SEEN


class UpsldcMonitorStatus(BaseModel):
    monitor_enabled: bool
    source_name: str
    source_page_url: str
    top_n: int
    configured_schedule: str
    last_monitor_run_at: datetime | None = None
    last_monitor_status: str | None = None  # COMPLETED | FAILED | None
    latest_detected_variable_cost_reports: list[DetectedReportItem] = []
    latest_new_report_count: int | None = None
    latest_existing_report_count: int | None = None
    last_error_safe_message: str | None = None


class SchedulerStatus(BaseModel):
    scheduler_enabled: bool
    scheduler_timezone: str
    scheduler_running: bool
    registered_jobs: list[SchedulerJobStatus]
    last_event: LastSchedulerEvent | None = None
    upsldc_monitor: UpsldcMonitorStatus | None = None
    limitation: str = (
        "Scheduler observability is read-only. No manual job triggers are exposed."
    )
