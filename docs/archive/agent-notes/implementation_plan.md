# Milestone 9B Part 2 — UPSLDC PDF Download, Archival, and Pending Review

## Overview

Extend the Milestone 9B Part 1 monitor to download only newly detected Variable Cost PDFs,
save them to git-ignored local storage, and create document metadata records flagged
`needs_review=True` / `review_status="pending_review"`. No parsing, no extraction,
no auto-approval, and no optimization interaction.

---

## Design Principles

1. **Never use `upload_and_parse_variable_cost_pdf()`** — that function auto-approves and triggers extraction.
2. **One new archive function** in `upsldc_monitor_service.py` handles download + safe store.
3. **Document record created with** `needs_review=True`, `review_status="pending_review"`, `source="SCHEDULER"`.
4. **Duplicate guard** — `sha256_hash` unique constraint blocks re-archiving the same PDF bytes.
5. **`UpsldcMonitoredReport` updated** with the linked `document_id` after archival.
6. **PDF download happens only for `NEW_DETECTED` reports** — never for `EXISTING_SEEN`.
7. **Bounded retry** — one attempt per PDF. Any download failure is logged and audited, not crashed.
8. **PDFs are already git-ignored** via `storage/documents/*` in `backend/.gitignore`.

---

## Proposed Changes

### monitor_models.py — Add `document_id` field

Link a monitored report row to its archived document once downloaded.

### upsldc_monitor_service.py — Add PDF download + archive step

New internal function `_download_and_archive_pdf(db, report_entry, run_id)`:
- `httpx.Client` GET to `report_url` with configurable timeout
- PDF content-type validation (`application/pdf` or `application/octet-stream`)
- Max size guard (configurable; default 35 MB from existing `document_max_upload_size_bytes`)
- `sha256` → duplicate check via `repository.get_document_by_hash`
- `save_file(content, filename, subfolder="variable_cost_pdf")` — uses existing storage helper
- `repository.create_document(...)` with `needs_review=True`, `review_status="pending_review"`
- `audit_service.record(action="UPSLDC_PDF_ARCHIVED", actor_type="SYSTEM", source="SCHEDULER")`
- Update `UpsldcMonitoredReport.document_id`
- If download fails → `audit_service.record(action="UPSLDC_PDF_DOWNLOAD_FAILED", ...)`; preserve monitoring row

`run_monitor()` extended to call archive step for each new detection only.

### config.py — Add PDF max size config

Reuse `document_max_upload_size_bytes` (already exists). No new config needed.

### Audit events added

| Action | When |
|---|---|
| `UPSLDC_PDF_ARCHIVED` | PDF downloaded and stored successfully |
| `UPSLDC_PDF_DOWNLOAD_FAILED` | PDF fetch failed; monitoring row preserved |
| `UPSLDC_PDF_DUPLICATE_SKIPPED` | SHA-256 already in documents table |

### monitor_models.py — New field

`document_id` (UUID, nullable FK to `documents.id`) — set after successful archival.

### Alembic migration — Add `document_id` column

### Tests — test_upsldc_monitor.py additions

7 new tests:
1. PDF downloaded for new detection, document created with `needs_review=True`
2. No PDF downloaded for existing detection
3. Duplicate PDF hash skipped without re-archiving
4. PDF download failure creates audit event, monitoring row preserved
5. PDF content-type mismatch rejected (not archived)
6. Oversized PDF rejected (not archived)
7. All 90 existing tests still pass

---

## Verification

- `pytest backend/tests/` — all ≥ 97 tests pass
- `ruff check backend/` — clean
- `npm run build` — frontend unaffected
- `git status` — no PDF files tracked
