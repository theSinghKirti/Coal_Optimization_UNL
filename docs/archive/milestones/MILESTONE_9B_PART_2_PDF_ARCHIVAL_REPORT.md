# Milestone 9B Part 2 — UPSLDC PDF Download, Archival, and Pending Review

## Overview

Extended the 9B Part 1 monitor to download newly detected Variable Cost PDFs, archive them
in git-ignored local storage, and create Document metadata records flagged
`needs_review=True` / `review_status="pending_review"`. No parsing, no extraction,
no auto-approval, and no optimization interaction.

**Final result: 97/97 tests passed · ruff clean · frontend build unaffected**

---

## 1. Files Changed

| File | Action | Purpose |
|---|---|---|
| [monitor_models.py](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/scheduler/monitor_models.py) | Modified | Added `document_id` nullable FK to `documents.id` |
| [upsldc_monitor_service.py](file:///c:/Users/itisa/Desktop/mdsir/backend/app/modules/scheduler/upsldc_monitor_service.py) | Modified | Added `fetch_pdf_bytes()` and `_archive_pdf()` functions; extended `run_monitor()` |
| [d2e3f4a5b6c7_add_document_id.py](file:///c:/Users/itisa/Desktop/mdsir/backend/alembic/versions/d2e3f4a5b6c7_add_document_id_to_upsldc_monitored.py) | New | Alembic migration adding `document_id` column |
| [test_upsldc_monitor.py](file:///c:/Users/itisa/Desktop/mdsir/backend/tests/test_upsldc_monitor.py) | Modified | Added 7 Part 2 archival tests; updated test 16 to reflect new HTTP boundary |

---

## 2. PDF Archival Flow

```
run_monitor()
├── fetch listing page HTML (1 request)
├── parse top-N PDF links
├── for each VC report:
│   ├── check upsldc_monitored_reports (URL hash)
│   ├── [NEW_DETECTED]
│   │   ├── insert UpsldcMonitoredReport row
│   │   ├── emit UPSLDC_VARIABLE_COST_REPORT_NEW_DETECTED audit
│   │   └── _archive_pdf()
│   │       ├── fetch_pdf_bytes() → httpx GET PDF URL
│   │       ├── validate content-type (must be PDF-like)
│   │       ├── validate size ≤ document_max_upload_size_bytes
│   │       ├── compute SHA-256 → check documents table (duplicate)
│   │       ├── [DUPLICATE] → link document_id, emit UPSLDC_PDF_DUPLICATE_SKIPPED
│   │       ├── [NEW] → save_file() → storage/documents/variable_cost_pdf/
│   │       │         → create Document(needs_review=True, review_status="pending_review")
│   │       │         → emit UPSLDC_PDF_ARCHIVED
│   │       └── [FAILURE] → emit UPSLDC_PDF_DOWNLOAD_FAILED; preserve monitor row
│   └── [EXISTING_SEEN]
│       └── update last_seen_at, last_check_run_id only — NO re-download
└── emit UPSLDC_MONITOR_COMPLETED
```

---

## 3. Document Record Properties

| Field | Value | Reason |
|---|---|---|
| `document_type` | `"VARIABLE_COST_PDF"` | Matches existing type enum |
| `needs_review` | `True` | Requires manual operator review |
| `review_status` | `"pending_review"` | Distinguishes from API-uploaded docs (which default to "approved") |
| `plant_id` | `null` | Not resolved at archival; operator resolves after review |
| `notes` | Source URL + "Pending manual review" | Traceability |
| `actor_type` | `"SYSTEM"` | Not from API |
| `source` | `"SCHEDULER"` | Audit trace |

> [!IMPORTANT]
> No VariableCost rows are created. The PDF is never parsed by `variable_cost_parser`.
> The document only enters the optimization pipeline after an operator explicitly approves it via the existing review workflow.

---

## 4. Duplicate Protection — Two Layers

**Layer 1 — URL hash (monitor level):**
- `(source_name, report_url_hash)` unique constraint on `upsldc_monitored_reports`
- Same PDF URL → `EXISTING_SEEN`, no re-download

**Layer 2 — SHA-256 content hash (document level):**
- `sha256_hash` unique constraint on `documents`
- Same PDF bytes → `UPSLDC_PDF_DUPLICATE_SKIPPED`, links existing document
- Protects against two different URLs serving the same PDF content

---

## 5. Failure Handling

All failure modes are safe and non-fatal:

| Failure | Behaviour |
|---|---|
| Page unreachable | `UPSLDC_MONITOR_FAILED` audit; no monitor rows written |
| PDF connection error | `UPSLDC_PDF_DOWNLOAD_FAILED` audit; monitor row preserved with `document_id=null` |
| Wrong content-type | `UPSLDC_PDF_DOWNLOAD_FAILED` audit; not archived |
| Oversized PDF | `UPSLDC_PDF_DOWNLOAD_FAILED` audit; not archived |
| Empty PDF response | `UPSLDC_PDF_DOWNLOAD_FAILED` audit; not archived |
| Local storage write failure | `UPSLDC_PDF_DOWNLOAD_FAILED` audit; monitor row preserved |
| Unexpected exception | Logged; `UPSLDC_MONITOR_FAILED` audit; no crash |

---

## 6. New Audit Events

| Action | actor_type | source | When |
|---|---|---|---|
| `UPSLDC_PDF_ARCHIVED` | SYSTEM | SCHEDULER | PDF downloaded and stored |
| `UPSLDC_PDF_DOWNLOAD_FAILED` | SYSTEM | SCHEDULER | Any download/validation failure |
| `UPSLDC_PDF_DUPLICATE_SKIPPED` | SYSTEM | SCHEDULER | SHA-256 already in documents table |

---

## 7. Git Tracking — PDFs Never Committed

PDFs are saved to `storage/documents/variable_cost_pdf/` which is covered by:

```gitignore
storage/documents/*           # in backend/.gitignore
storage/                      # in root .gitignore
```

`git status` will not show any PDF files.

---

## 8. MonitorRunResult — New Field

```python
@dataclass
class MonitorRunResult:
    ...
    archived_pdf_count: int = 0   # How many PDFs were successfully archived this run
```

---

## 9. Test Coverage

| # | Test | Result |
|---|---|---|
| 1–15 | All Part 1 tests (unchanged) | ✅ PASS |
| 16 | HTTP boundary: exactly 1 listing page fetch; no re-fetch for existing | ✅ PASS |
| 17 | Other modules smoke test | ✅ PASS |
| 18 | PDF downloaded for new detection; `needs_review=True`; no VariableCost rows | ✅ PASS |
| 19 | No PDF downloaded for existing (EXISTING_SEEN) detection | ✅ PASS |
| 20 | Duplicate SHA-256 skipped; UPSLDC_PDF_DUPLICATE_SKIPPED emitted | ✅ PASS |
| 21 | PDF download failure → audit event; monitor row preserved | ✅ PASS |
| 22 | Wrong content-type (text/html) rejected | ✅ PASS |
| 23 | Oversized PDF (>35 MB) rejected | ✅ PASS |
| 24 | Archived document: `needs_review=True`, `pending_review`, zero VariableCost rows | ✅ PASS |

**Total: 97 passed in 11.34s**

---

## 10. Explicit Safety Confirmations

> ✅ **No PDF was auto-approved or auto-activated.**
>
> ✅ **No VariableCost rows were created. The PDF parser was not called.**
>
> ✅ **No optimization run was triggered or modified.**
>
> ✅ **No frontend code was changed.**
>
> ✅ **PDFs are stored in git-ignored local storage.**
>
> ✅ **Existing reports are never re-downloaded.**
>
> ✅ **All failures are audited and non-fatal — no crashes.**
>
> ✅ **Document records require explicit operator review before entering the pipeline.**
