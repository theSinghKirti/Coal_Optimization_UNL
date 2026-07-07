# Milestone 9A — Scheduler Foundation and Safe Job Observability

## Overview

Built a production-safe background scheduler foundation using APScheduler. The scheduler is disabled by default, fully controlled by environment configuration, and emits structured audit events to PostgreSQL on every job cycle.

---

## Changes Made

### Configuration

#### [config.py](file:///c:/Users/itisa/Desktop/mdsir/backend/app/core/config.py)
Added three new scheduler configuration fields:
- `scheduler_timezone` — defaults to `Asia/Kolkata`
- `scheduler_document_check_hour` — defaults to `6`
- `scheduler_document_check_minute` — defaults to `0`

Also updated both [.env](file:///c:/Users/itisa/Desktop/mdsir/backend/.env) and [.env.example](file:///c:/Users/itisa/Desktop/mdsir/backend/.env.example) with the new variables.

---

### Scheduler Jobs

#### [jobs.py](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/scheduler/jobs.py)
Rebuilt completely. Key behaviors:
- `start_scheduler()` — only starts when `SCHEDULER_ENABLED=true`. Guards against duplicate startup with a global instance check. Instantiates `BackgroundScheduler(timezone=settings.scheduler_timezone)`.
- Registers `DOCUMENT_MONITORING_HEARTBEAT` cron job at the configured hour/minute in `Asia/Kolkata`.
- `_heartbeat_job()` — writes `SCHEDULER_JOB_STARTED` then `SCHEDULER_JOB_COMPLETED` audit events (or `SCHEDULER_JOB_FAILED` on error) using `actor_type="SYSTEM"` and `source="SCHEDULER"`.
- `shutdown_scheduler()` — gracefully shuts down and clears the global instance.
- `get_scheduler()` — returns the current scheduler instance (or `None` if disabled).

---

### Scheduler Schemas

#### [schemas.py](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/scheduler/schemas.py)
Added three new Pydantic models:
- `SchedulerJobStatus` — per-job metadata (id, name, trigger, next_run_time)
- `LastSchedulerEvent` — last audit event from the scheduler (action, occurred_at, metadata)
- `SchedulerStatus` — full read-only response shape with all fields

---

### Scheduler Router

#### [router.py](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/scheduler/router.py)
Replaced previous trigger endpoints with a single read-only endpoint:

```
GET /api/v1/scheduler/status
```

Returns:
- `scheduler_enabled` — reflects `SCHEDULER_ENABLED` env var
- `scheduler_timezone` — `Asia/Kolkata` (default)
- `scheduler_running` — live APScheduler state
- `registered_jobs` — list of all registered jobs with triggers and next run times
- `last_event` — most recent `SCHEDULER`-sourced audit log entry
- `limitation` — static informational message

---

### Tests

#### [test_scheduler_observability.py](file:///c:/Users/itisa/Desktop/mdsir/backend/tests/test_scheduler_observability.py)
5 new tests covering all requirements:

| Test | Validates |
|---|---|
| `test_scheduler_disabled_by_default` | Disabled state returns safe structure |
| `test_scheduler_enabled_in_controlled_setup` | Scheduler starts, registers job, shuts down cleanly |
| `test_heartbeat_job_creates_audit_events` | STARTED + COMPLETED events written with SYSTEM/SCHEDULER metadata |
| `test_status_endpoint_creates_no_audit_event` | GET /status is entirely read-only |
| `test_no_scheduler_mutation_endpoints` | POST/PUT/DELETE and manual trigger routes return 404/405 |

---

## Test Results

```
72 passed in 10.15s
```

All 72 tests pass (67 pre-existing + 5 new scheduler tests). Ruff reports zero lint errors.

---

## Live API Validation

`GET http://127.0.0.1:8001/api/v1/scheduler/status` returned:

```json
{
  "scheduler_enabled": false,
  "scheduler_timezone": "Asia/Kolkata",
  "scheduler_running": false,
  "registered_jobs": [],
  "last_event": {
    "action": "SCHEDULER_JOB_COMPLETED",
    "occurred_at": "2026-07-07T01:20:01.383030Z",
    "metadata": {
      "job_name": "DOCUMENT_MONITORING_HEARTBEAT",
      "scheduler_timezone": "Asia/Kolkata",
      "scheduled_run_time": "2026-07-07T01:20:01.337762+00:00",
      "result": "success"
    }
  },
  "limitation": "External document source monitoring is not configured in Milestone 9A."
}
```

✅ Scheduler correctly disabled by default  
✅ Timezone correctly set to `Asia/Kolkata`  
✅ Last event reflects the heartbeat test run  
✅ No registered jobs when disabled  
✅ Limitation message present  
