# Milestone 9B Part 1 — UPSLDC MOD Report Monitoring and Dry-Run Detection

## Overview

Built a production-safe backend monitor that fetches the UPSLDC MOD Reports listing page, detects Variable Cost / Variable Charges reports in the top N rows, and stores only safe monitoring metadata in a new table. No PDF files are downloaded, uploaded, or parsed. No records are approved or activated.

---

## 1. Files Changed

| File | Action | Purpose |
|---|---|---|
| [config.py](file:///c:/Users/itisa/Desktop/mdsir/backend/app/core/config.py) | Modified | Added 8 new monitor settings |
| [.env](file:///c:/Users/itisa/Desktop/mdsir/backend/.env) | Modified | Added monitor env vars |
| [.env.example](file:///c:/Users/itisa/Desktop/mdsir/backend/.env.example) | Modified | Added monitor env examples |
| [monitor_models.py](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/scheduler/monitor_models.py) | New | ORM model `UpsldcMonitoredReport` |
| [upsldc_monitor_service.py](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/scheduler/upsldc_monitor_service.py) | New | Fetch, parse, classify, detect — no PDF download |
| [jobs.py](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/scheduler/jobs.py) | Modified | Added `_upsldc_monitor_job`, conditional job registration |
| [schemas.py](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/scheduler/schemas.py) | Modified | Added `DetectedReportItem`, `UpsldcMonitorStatus`; extended `SchedulerStatus` |
| [router.py](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/scheduler/router.py) | Modified | Extend `GET /scheduler/status` with `upsldc_monitor` block |
| [conftest.py](file:///c:/Users/itisa/Desktop/mdsir/backend/tests/conftest.py) | Modified | Import `monitor_models` so test DB creates the table |
| [c1d2e3f4a5b6_add_upsldc_monitored_reports.py](file:///c:/Users/itisa/Desktop/mdsir/backend/alembic/versions/c1d2e3f4a5b6_add_upsldc_monitored_reports.py) | New | Alembic migration for `upsldc_monitored_reports` table |
| [test_upsldc_monitor.py](file:///c:/Users/itisa/Desktop/mdsir/backend/tests/test_upsldc_monitor.py) | New | 17 focused tests, all HTTP mocked |
| [test_scheduler_observability.py](file:///c:/Users/itisa/Desktop/mdsir/backend/tests/test_scheduler_observability.py) | Modified | Updated `limitation` string assertion to match new text |

---

## 2. New Environment Settings

| Variable | Default | Description |
|---|---|---|
| `UPSLDC_MOD_REPORTS_URL` | `https://www.upsldc.org/schmod` | Source page URL — configurable |
| `UPSLDC_MONITOR_ENABLED` | `false` | Monitor must be explicitly enabled |
| `UPSLDC_MONITOR_TOP_N` | `10` | Max report rows to inspect per run |
| `UPSLDC_MONITOR_TIMEOUT_SECONDS` | `20` | HTTP request timeout |
| `UPSLDC_MONITOR_USER_AGENT` | `CODSP-UPSLDC-Monitor/1.0` | Descriptive UA header |
| `UPSLDC_MONITOR_SCHEDULE_DAYS` | `2,16` | Comma-separated day-of-month |
| `UPSLDC_MONITOR_HOUR` | `9` | Run hour (IST, Asia/Kolkata) |
| `UPSLDC_MONITOR_MINUTE` | `0` | Run minute |

---

## 3. Source Parsing Strategy

- **HTTP Client:** `httpx` only. Single request per monitor run, no retries that multiply requests.
- **Content-Type validation:** Page must return `text/html` or `text/`; other types are rejected.
- **Size guard:** Response capped at 5 MB before decoding.
- **HTML parser:** Python stdlib `html.parser.HTMLParser` — no external BeautifulSoup or lxml dependency needed.
- **Extraction logic:** `_PdfLinkExtractor` walks all `<a href="...pdf">` links; stores anchor text as title.
- **Top-N limit:** Only the first `UPSLDC_MONITOR_TOP_N` discovered PDF links are examined.
- **Absolute URL resolution:** All relative URLs are resolved to absolute using `urljoin`.
- **Never fetched:** PDF byte content is never requested; only the listing page HTML is fetched.

---

## 4. Variable Cost Matching Rules

Exact keyword matching — no fuzzy logic. Title must contain at least one of:

- `variable charges`
- `variable charge`
- `variable cost`
- `mod stack of variable charges`

Matching is case-insensitive against the lowercase normalized title.

Examples that match:
- `Variable Charges effective from 01-07-2026 to 15-07-2026` ✅
- `Revised State MOD Stack of Variable Charges (VC)` ✅
- `State Variable Cost Report` ✅

Examples that do NOT match:
- `State MOD Dispatch Schedule` ❌
- `MOD Merit Order Dispatch` ❌

---

## 5. Duplicate-Detection Strategy

**Fingerprint:** `sha256(report_url.strip().lower())`

**Uniqueness constraint:** `(source_name, report_url_hash)` — database-level constraint prevents duplicates even under concurrent writes.

**Detection flow per report:**
1. Compute `url_hash = sha256(normalized PDF URL)`
2. Query `upsldc_monitored_reports` for matching `(source_name, url_hash)`
3. If not found → `NEW_DETECTED` → insert new row + emit audit event
4. If found → `EXISTING_SEEN` → update `last_seen_at`, `last_check_run_id`, `is_currently_visible` only

No new-detection audit event is emitted on subsequent runs for the same URL.

---

## 6. Revised Report Handling

A revised report that publishes a **new PDF URL** always gets a new `url_hash`, so it is treated as a new detection even if:
- The report title is identical or very similar.
- The effective date range overlaps with a previous report.

This avoids masking important changes behind deduplication. The system does **not** automatically decide which report is operationally active — that remains a manual operator decision.

---

## 7. Effective Date Parsing Policy

- **Pattern:** Regex `(\d{1,2}-\d{1,2}-\d{4})\s+to\s+(\d{1,2}-\d{1,2}-\d{4})` against the raw title.
- **Format:** `dd-mm-yyyy` — parsed with `strptime("%d-%m-%Y")`.
- **Success:** Both `effective_from` and `effective_to` stored as `Date` columns.
- **Failure / ambiguity:** Both fields remain `null`. Original title is always preserved.
- **Never guesses:** Partial matches or `ValueError` from `strptime` → null, not estimated dates.
- **Not used for optimization:** Effective dates are stored for metadata only; they do not activate or replace any Variable Cost data.

---

## 8. Scheduler Schedule and Non-Overlap Protection

| Property | Value |
|---|---|
| Job ID | `UPSLDC_VARIABLE_COST_MONITOR` |
| Trigger | `CronTrigger(day="2,16", hour=9, minute=0, timezone="Asia/Kolkata")` |
| `max_instances` | `1` — prevents overlapping executions |
| `coalesce` | `True` — skips missed runs, does not pile them up |
| `replace_existing` | `True` — safe across lifespan reloads |
| Registration guard | Job only registered when `UPSLDC_MONITOR_ENABLED=true` |
| Coexistence | Runs safely alongside `DOCUMENT_MONITORING_HEARTBEAT` |
| Scheduler timezone | `Asia/Kolkata` (from `SCHEDULER_TIMEZONE`) |

---

## 9. Audit Events Added

| Action | actor_type | source | When |
|---|---|---|---|
| `UPSLDC_MONITOR_STARTED` | SYSTEM | SCHEDULER | Once per run, at start |
| `UPSLDC_MONITOR_COMPLETED` | SYSTEM | SCHEDULER | On successful run completion |
| `UPSLDC_MONITOR_FAILED` | SYSTEM | SCHEDULER | When page is unreachable or unexpected error |
| `UPSLDC_VARIABLE_COST_REPORT_NEW_DETECTED` | SYSTEM | SCHEDULER | Once per newly discovered report URL |

**Metadata stored:** run_id, source_page_url, scanned_row_count, variable_cost_count, new_report_count, existing_report_count, report_title, report_url_hash, effective date range.

**Never stored in metadata:** raw HTML, PDF bytes, cookies, headers, secrets, full stack traces.

---

## 10. Scheduler Status API Fields Added

`GET /api/v1/scheduler/status` now returns an `upsldc_monitor` object:

```json
{
  "upsldc_monitor": {
    "monitor_enabled": false,
    "source_name": "UPSLDC_SCHMOD",
    "source_page_url": "https://www.upsldc.org/schmod",
    "top_n": 10,
    "configured_schedule": "days=2,16 09:00 Asia/Kolkata",
    "last_monitor_run_at": null,
    "last_monitor_status": null,
    "latest_detected_variable_cost_reports": [],
    "latest_new_report_count": null,
    "latest_existing_report_count": null,
    "last_error_safe_message": null
  }
}
```

After a successful run, `latest_detected_variable_cost_reports` lists reports with:
`title`, `report_url`, `effective_from`, `effective_to`, `first_seen_at`, `last_seen_at`, `detection_status`.

---

## 11. Test Coverage

| # | Test | Result |
|---|---|---|
| 1 | Monitor disabled by default | ✅ PASS |
| 2 | No UPSLDC job registered when monitor disabled | ✅ PASS |
| 3 | Top 10 rows correctly detects only VC reports | ✅ PASS |
| 4 | PDF URLs extracted and resolved to absolute form | ✅ PASS |
| 5 | Revised VC report classified correctly | ✅ PASS |
| 6 | Effective dates parsed from valid title | ✅ PASS |
| 7 | Uncertain/missing dates remain null | ✅ PASS |
| 7b | Invalid date format yields null | ✅ PASS |
| 8 | New report creates metadata + audit event | ✅ PASS |
| 9 | Repeated run creates no duplicate metadata | ✅ PASS |
| 10 | Repeated run creates no duplicate new-detection events | ✅ PASS |
| 11 | Revised report with new URL is new detection | ✅ PASS |
| 12 | Source failure creates safe audit failure event | ✅ PASS |
| 13 | Source failure preserves previous metadata | ✅ PASS |
| 14 | Scheduler status API includes safe monitor state | ✅ PASS |
| 15 | GET scheduler status creates no audit event | ✅ PASS |
| 16 | No PDF download request occurs | ✅ PASS |
| 17 | Other modules (health, dashboard, recommendations) unaffected | ✅ PASS |

**Final result: 90 passed in 7.50s** (72 pre-existing + 18 new; 5 scheduler + 17 monitor + 1 revised observability)

---

## 12. Local Dry-Run Verification

A controlled dry-run script is available at `scratch/dryrun_upsldc_monitor.py` in the artifacts directory. It can be run locally to fetch the live UPSLDC page and inspect audit logs. It is **not** exposed as any API endpoint.

Dry run should:
- Set `UPSLDC_MONITOR_ENABLED=true` temporarily
- Call `run_monitor(db)` once
- Print detected reports
- Inspect `GET /api/v1/scheduler/status` and `GET /api/v1/audit-logs?action=UPSLDC_VARIABLE_COST_REPORT_NEW_DETECTED`

---

## 13. Explicit Confirmation

> ✅ **No PDF was downloaded, uploaded, extracted, approved, or activated in this milestone.**
>
> ✅ No document records were created in the document store.
>
> ✅ No Variable Cost extraction was triggered.
>
> ✅ No optimization run was modified.
>
> ✅ No frontend code was changed.
>
> ✅ The monitor runs only on configured days (2nd, 16th) in `Asia/Kolkata` timezone.
>
> ✅ The monitor is disabled by default (`UPSLDC_MONITOR_ENABLED=false`).
