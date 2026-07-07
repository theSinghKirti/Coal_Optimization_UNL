"""Tests for Milestone 9B Parts 1 & 2: UPSLDC MOD Report Monitor and PDF Archival.

All HTTP calls are mocked — the real UPSLDC website is never contacted.
PDFs are written to a temp directory during tests; production storage is unaffected.
"""

from unittest.mock import MagicMock, patch

from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.documents.models import Document
from app.modules.scheduler.monitor_models import UpsldcMonitoredReport
from app.modules.scheduler.upsldc_monitor_service import (
    is_variable_cost_report,
    parse_effective_dates,
    parse_report_rows,
    run_monitor,
)

# ---------------------------------------------------------------------------
# Mock HTML fixtures
# ---------------------------------------------------------------------------

_VC_JULY = "Variable Charges effective from 01-07-2026 to 15-07-2026"
_VC_REVISED = "Revised State MOD Stack of Variable Charges (VC) 01-07-2026 to 15-07-2026"
_VC_JUNE = "Variable Charges effective from 01-06-2026 to 15-06-2026"
_UNRELATED = "State MOD Dispatch Schedule"

_HTML_WITH_VC_REPORTS = f"""
<html><body>
<table>
<tr><td><a href="/files/vc_july_2026.pdf">{_VC_JULY}</a></td></tr>
<tr><td><a href="/files/vc_revised_july_2026.pdf">{_VC_REVISED}</a></td></tr>
<tr><td><a href="/files/unrelated_mod.pdf">{_UNRELATED}</a></td></tr>
<tr><td><a href="/files/vc_june_2026.pdf">{_VC_JUNE}</a></td></tr>
</table>
</body></html>
"""

_HTML_NO_DATES = """
<html><body>
<a href="/files/vc_nodates.pdf">Variable Cost Report without dates</a>
</body></html>
"""

_SOURCE_URL = "https://www.upsldc.org/schmod"


# ---------------------------------------------------------------------------
# 1. Monitor disabled by default
# ---------------------------------------------------------------------------

def test_monitor_disabled_by_default():
    from app.core.config import get_settings
    s = get_settings()
    assert s.upsldc_monitor_enabled is False


# ---------------------------------------------------------------------------
# 2. No UPSLDC job registered when monitor disabled
# ---------------------------------------------------------------------------

def test_no_upsldc_job_when_monitor_disabled():
    from unittest.mock import patch

    from app.modules.scheduler.jobs import shutdown_scheduler, start_scheduler

    with patch("app.modules.scheduler.jobs.settings.scheduler_enabled", True), \
         patch("app.modules.scheduler.jobs.settings.upsldc_monitor_enabled", False):
        scheduler = start_scheduler()
        try:
            assert scheduler is not None
            job_ids = [j.id for j in scheduler.get_jobs()]
            assert "UPSLDC_VARIABLE_COST_MONITOR" not in job_ids
            assert "DOCUMENT_MONITORING_HEARTBEAT" in job_ids
        finally:
            shutdown_scheduler()


# ---------------------------------------------------------------------------
# 3. Parse top 10 rows correctly detects only VC reports from mocked HTML
# ---------------------------------------------------------------------------

def test_parse_rows_detects_only_vc_reports():
    rows = parse_report_rows(_HTML_WITH_VC_REPORTS, _SOURCE_URL, top_n=10)
    assert len(rows) == 4  # 4 PDF links total

    vc_rows = [(t, u) for t, u in rows if is_variable_cost_report(t)]
    assert len(vc_rows) == 3  # 3 VC reports; "State MOD Dispatch Schedule" is NOT VC
    vc_titles = [t for t, _ in vc_rows]
    assert any("Variable Charges" in t for t in vc_titles)
    assert any("Revised State MOD Stack" in t for t in vc_titles)
    # Unrelated MOD report must be excluded
    non_vc = [(t, u) for t, u in rows if not is_variable_cost_report(t)]
    assert len(non_vc) == 1
    assert "Dispatch Schedule" in non_vc[0][0]


# ---------------------------------------------------------------------------
# 4. PDF URLs are extracted and resolved to absolute form
# ---------------------------------------------------------------------------

def test_pdf_url_absolute_resolution():
    rows = parse_report_rows(_HTML_WITH_VC_REPORTS, _SOURCE_URL, top_n=10)
    for _title, url in rows:
        assert url.startswith("https://")
        assert url.endswith(".pdf")


# ---------------------------------------------------------------------------
# 5. Revised report with different URL is a separate entry
# ---------------------------------------------------------------------------

def test_is_variable_cost_report_classifies_revised():
    assert is_variable_cost_report("Revised State MOD Stack of Variable Charges (VC)")
    assert is_variable_cost_report("Variable Charges effective from 01-07-2026 to 15-07-2026")
    assert is_variable_cost_report("Variable Cost Report")
    assert is_variable_cost_report("MOD Stack of Variable Charges")


# ---------------------------------------------------------------------------
# 6. Effective dates parsed when title format is valid
# ---------------------------------------------------------------------------

def test_effective_dates_parsed_from_valid_title():
    title = "Variable Charges effective from 01-07-2026 to 15-07-2026"
    d_from, d_to = parse_effective_dates(title)
    assert d_from is not None
    assert d_to is not None
    assert d_from.year == 2026
    assert d_from.month == 7
    assert d_from.day == 1
    assert d_to.day == 15


# ---------------------------------------------------------------------------
# 7. Uncertain / missing dates remain null
# ---------------------------------------------------------------------------

def test_effective_dates_null_when_absent():
    title = "Variable Cost Report without dates"
    d_from, d_to = parse_effective_dates(title)
    assert d_from is None
    assert d_to is None


def test_effective_dates_null_on_invalid_format():
    title = "Variable Charges from 99-99-2026 to 00-00-0000"
    d_from, d_to = parse_effective_dates(title)
    assert d_from is None
    assert d_to is None


# ---------------------------------------------------------------------------
# 8. New report creates one metadata record and one new-detected audit event
# ---------------------------------------------------------------------------

def test_new_report_creates_metadata_and_audit_event(db_session):
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.headers = {"content-type": "text/html; charset=utf-8"}
    fake_response.content = _HTML_WITH_VC_REPORTS.encode()
    fake_response.raise_for_status = lambda: None

    fake_client = MagicMock()
    fake_client.__enter__ = lambda s: fake_client
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.get = MagicMock(return_value=fake_response)

    with patch("app.modules.scheduler.upsldc_monitor_service.httpx.Client", return_value=fake_client):
        result = run_monitor(db_session)

    assert result.source_reachable is True
    assert result.new_report_count >= 1

    # Check DB record
    rows = db_session.execute(
        select(UpsldcMonitoredReport).where(UpsldcMonitoredReport.report_type == "VARIABLE_COST")
    ).scalars().all()
    assert len(rows) >= 1

    # Check audit event
    audit_rows = db_session.execute(
        select(AuditLog).where(AuditLog.action == "UPSLDC_VARIABLE_COST_REPORT_NEW_DETECTED")
    ).scalars().all()
    assert len(audit_rows) >= 1
    assert audit_rows[0].actor_type == "SYSTEM"
    assert audit_rows[0].source == "SCHEDULER"


# ---------------------------------------------------------------------------
# 9. Repeated run does not create duplicate metadata records
# ---------------------------------------------------------------------------

def test_repeated_run_no_duplicate_metadata(db_session):
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.headers = {"content-type": "text/html; charset=utf-8"}
    fake_response.content = _HTML_WITH_VC_REPORTS.encode()
    fake_response.raise_for_status = lambda: None

    fake_client = MagicMock()
    fake_client.__enter__ = lambda s: fake_client
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.get = MagicMock(return_value=fake_response)

    with patch("app.modules.scheduler.upsldc_monitor_service.httpx.Client", return_value=fake_client):
        run_monitor(db_session)
        run_monitor(db_session)

    rows = db_session.execute(
        select(UpsldcMonitoredReport).where(UpsldcMonitoredReport.report_type == "VARIABLE_COST")
    ).scalars().all()

    # Unique by report_url_hash — no duplicates
    hashes = [r.report_url_hash for r in rows]
    assert len(hashes) == len(set(hashes))


# ---------------------------------------------------------------------------
# 10. Repeated run does not create noisy duplicate new-report audit events
# ---------------------------------------------------------------------------

def test_repeated_run_no_duplicate_new_detected_events(db_session):
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.headers = {"content-type": "text/html; charset=utf-8"}
    fake_response.content = _HTML_WITH_VC_REPORTS.encode()
    fake_response.raise_for_status = lambda: None

    fake_client = MagicMock()
    fake_client.__enter__ = lambda s: fake_client
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.get = MagicMock(return_value=fake_response)

    with patch("app.modules.scheduler.upsldc_monitor_service.httpx.Client", return_value=fake_client):
        run_monitor(db_session)
        run2 = run_monitor(db_session)

    # Second run should have 0 new, all existing
    assert run2.new_report_count == 0
    assert run2.existing_report_count >= 1


# ---------------------------------------------------------------------------
# 11. Revised report with new PDF URL treated as new
# ---------------------------------------------------------------------------

_HTML_REVISED_NEW_URL = f"""
<html><body>
<a href="/files/vc_revised_v2.pdf">{_VC_REVISED}</a>
</body></html>
"""

_HTML_REVISED_NEW_URL_V2 = f"""
<html><body>
<a href="/files/vc_revised_v3.pdf">{_VC_REVISED}</a>
</body></html>
"""


def test_revised_report_new_url_is_new_detection(db_session):
    def make_fake_client(html: str):
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.headers = {"content-type": "text/html; charset=utf-8"}
        fake_response.content = html.encode()
        fake_response.raise_for_status = lambda: None
        fake_client = MagicMock()
        fake_client.__enter__ = lambda s: fake_client
        fake_client.__exit__ = MagicMock(return_value=False)
        fake_client.get = MagicMock(return_value=fake_response)
        return fake_client

    with patch(
        "app.modules.scheduler.upsldc_monitor_service.httpx.Client",
        return_value=make_fake_client(_HTML_REVISED_NEW_URL),
    ):
        result1 = run_monitor(db_session)

    with patch(
        "app.modules.scheduler.upsldc_monitor_service.httpx.Client",
        return_value=make_fake_client(_HTML_REVISED_NEW_URL_V2),
    ):
        result2 = run_monitor(db_session)

    assert result1.new_report_count == 1
    assert result2.new_report_count == 1  # Different URL → new detection


# ---------------------------------------------------------------------------
# 12. Source timeout/failure creates safe audit failure event
# ---------------------------------------------------------------------------

def test_source_failure_creates_audit_failure_event(db_session):
    with patch("app.modules.scheduler.upsldc_monitor_service.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.side_effect = Exception("Connection timed out")

        result = run_monitor(db_session)

    assert result.source_reachable is False
    assert result.error_safe_message is not None

    audit_rows = db_session.execute(
        select(AuditLog).where(AuditLog.action == "UPSLDC_MONITOR_FAILED")
    ).scalars().all()
    assert len(audit_rows) >= 1
    assert audit_rows[0].actor_type == "SYSTEM"


# ---------------------------------------------------------------------------
# 13. Source failure preserves previous metadata
# ---------------------------------------------------------------------------

def test_source_failure_preserves_previous_metadata(db_session):
    # First: successful run
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.headers = {"content-type": "text/html; charset=utf-8"}
    fake_response.content = _HTML_WITH_VC_REPORTS.encode()
    fake_response.raise_for_status = lambda: None
    fake_client = MagicMock()
    fake_client.__enter__ = lambda s: fake_client
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.get = MagicMock(return_value=fake_response)

    with patch("app.modules.scheduler.upsldc_monitor_service.httpx.Client", return_value=fake_client):
        run_monitor(db_session)

    count_before = len(
        db_session.execute(select(UpsldcMonitoredReport)).scalars().all()
    )
    assert count_before >= 1

    # Second: failed run
    with patch("app.modules.scheduler.upsldc_monitor_service.httpx.Client") as mock_cls:
        mock_cls.return_value.__enter__.side_effect = Exception("Timeout")
        run_monitor(db_session)

    count_after = len(
        db_session.execute(select(UpsldcMonitoredReport)).scalars().all()
    )
    assert count_after == count_before  # No records deleted on failure


# ---------------------------------------------------------------------------
# 14. Scheduler status API shows safe monitor state
# ---------------------------------------------------------------------------

def test_scheduler_status_includes_upsldc_monitor(client):
    resp = client.get("/api/v1/scheduler/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "upsldc_monitor" in data
    monitor = data["upsldc_monitor"]
    assert monitor["monitor_enabled"] is False
    assert monitor["source_name"] == "UPSLDC_SCHMOD"
    assert "upsldc.org" in monitor["source_page_url"]
    assert "configured_schedule" in monitor
    assert "latest_detected_variable_cost_reports" in monitor


# ---------------------------------------------------------------------------
# 15. GET scheduler status creates no audit event
# ---------------------------------------------------------------------------

def test_get_scheduler_status_creates_no_audit_event(client, db_session):
    count_before = len(db_session.execute(select(AuditLog)).scalars().all())
    resp = client.get("/api/v1/scheduler/status")
    assert resp.status_code == 200
    count_after = len(db_session.execute(select(AuditLog)).scalars().all())
    assert count_before == count_after


# ---------------------------------------------------------------------------
# 16. HTTP boundary: listing page fetched exactly once per run; PDFs attempted
#     only for NEW_DETECTED reports — never for EXISTING_SEEN.
# ---------------------------------------------------------------------------

def test_no_duplicate_listing_page_requests(db_session, tmp_path):
    """Monitor fetches listing page exactly once per run regardless of report count."""
    page_fetch_count = [0]
    pdf_fetch_count = [0]

    def capturing_client(**kwargs):
        m = MagicMock()
        m.__exit__ = MagicMock(return_value=False)

        def fake_get(url, **kw):
            resp = MagicMock()
            resp.raise_for_status = lambda: None
            if url.endswith(".pdf"):
                pdf_fetch_count[0] += 1
                resp.headers = {"content-type": "application/pdf"}
                resp.content = b"%PDF fake"
            else:
                page_fetch_count[0] += 1
                resp.headers = {"content-type": "text/html"}
                resp.content = _HTML_WITH_VC_REPORTS.encode()
            resp.status_code = 200
            return resp

        m.__enter__ = lambda s: m
        m.get = fake_get
        return m

    with patch(
        "app.modules.scheduler.upsldc_monitor_service.httpx.Client",
        side_effect=capturing_client,
    ), patch(
        "app.modules.scheduler.upsldc_monitor_service.save_file",
        return_value=str(tmp_path / "vc.pdf"),
    ):
        run_monitor(db_session)

    # Exactly one listing page request per run
    assert page_fetch_count[0] == 1
    # PDF fetches happened only for VC reports (new detections)
    assert pdf_fetch_count[0] >= 1

    # Second run — same reports now EXISTING_SEEN; no new PDF fetches
    page_fetch_count[0] = 0
    pdf_fetch_count[0] = 0
    with patch(
        "app.modules.scheduler.upsldc_monitor_service.httpx.Client",
        side_effect=capturing_client,
    ), patch(
        "app.modules.scheduler.upsldc_monitor_service.save_file",
        return_value=str(tmp_path / "vc2.pdf"),
    ):
        run_monitor(db_session)

    assert page_fetch_count[0] == 1  # Still one listing page fetch
    assert pdf_fetch_count[0] == 0   # No PDF fetches for existing reports


# ---------------------------------------------------------------------------
# 17. Existing scheduler / other tests unaffected (smoke check)
# ---------------------------------------------------------------------------

def test_other_modules_still_work(client):
    """Smoke test: existing endpoints still respond after monitor code was added."""
    r1 = client.get("/api/v1/health")
    assert r1.status_code == 200

    r2 = client.get("/api/v1/dashboard/summary")
    assert r2.status_code == 200

    r3 = client.get("/api/v1/recommendations/latest")
    assert r3.status_code == 200


# ===========================================================================
# Milestone 9B Part 2 — PDF Archival tests (18–24)
# ===========================================================================

def _make_page_client(html: str):
    """Build a mock httpx client that returns HTML from the listing page."""
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.headers = {"content-type": "text/html; charset=utf-8"}
    fake_resp.content = html.encode()
    fake_resp.raise_for_status = lambda: None
    client = MagicMock()
    client.__enter__ = lambda s: client
    client.__exit__ = MagicMock(return_value=False)
    client.get = MagicMock(return_value=fake_resp)
    return client


def _make_pdf_content() -> bytes:
    return b"%PDF-1.4 fake pdf content for testing" + b"x" * 100


# ---------------------------------------------------------------------------
# 18. PDF downloaded for new detection, document created needs_review=True
# ---------------------------------------------------------------------------

def test_pdf_archived_for_new_detection(db_session, tmp_path):
    """New detection → PDF downloaded → Document record created with needs_review=True."""
    pdf_content = _make_pdf_content()

    page_client = _make_page_client(_HTML_WITH_VC_REPORTS)
    pdf_resp = MagicMock()
    pdf_resp.status_code = 200
    pdf_resp.headers = {"content-type": "application/pdf"}
    pdf_resp.content = pdf_content
    pdf_resp.raise_for_status = lambda: None
    pdf_client = MagicMock()
    pdf_client.__enter__ = lambda s: pdf_client
    pdf_client.__exit__ = MagicMock(return_value=False)
    pdf_client.get = MagicMock(return_value=pdf_resp)

    clients = [page_client, pdf_client, pdf_client, pdf_client]  # one page + one per VC PDF
    client_iter = iter(clients)

    with patch(
        "app.modules.scheduler.upsldc_monitor_service.httpx.Client",
        side_effect=lambda **kw: next(client_iter),
    ), patch(
        "app.modules.scheduler.upsldc_monitor_service.save_file",
        return_value=str(tmp_path / "test_vc.pdf"),
    ):
        result = run_monitor(db_session)

    assert result.new_report_count >= 1
    assert result.archived_pdf_count >= 1

    docs = db_session.execute(
        select(Document).where(Document.document_type == "VARIABLE_COST_PDF")
    ).scalars().all()
    assert len(docs) >= 1
    doc = docs[0]
    assert doc.needs_review is True
    assert doc.review_status == "pending_review"
    # Confirm no VariableCost rows created (no parsing triggered)
    from app.modules.documents.models import VariableCost
    vc_rows = db_session.execute(select(VariableCost)).scalars().all()
    assert len(vc_rows) == 0


# ---------------------------------------------------------------------------
# 19. No PDF downloaded for existing (EXISTING_SEEN) detection
# ---------------------------------------------------------------------------

def test_no_pdf_download_for_existing_detection(db_session, tmp_path):
    """Second run on same reports → no new PDF downloads."""
    pdf_content = _make_pdf_content()
    page_client = _make_page_client(_HTML_WITH_VC_REPORTS)
    pdf_resp = MagicMock()
    pdf_resp.status_code = 200
    pdf_resp.headers = {"content-type": "application/pdf"}
    pdf_resp.content = pdf_content
    pdf_resp.raise_for_status = lambda: None
    pdf_client = MagicMock()
    pdf_client.__enter__ = lambda s: pdf_client
    pdf_client.__exit__ = MagicMock(return_value=False)
    pdf_client.get = MagicMock(return_value=pdf_resp)

    calls_tracker: list[str] = []

    def capturing_client(**kwargs):
        capturing_client._call_count = getattr(capturing_client, "_call_count", 0) + 1
        if capturing_client._call_count == 1:
            return page_client  # first call is listing page
        calls_tracker.append("pdf_fetch")
        return pdf_client

    with patch(
        "app.modules.scheduler.upsldc_monitor_service.httpx.Client",
        side_effect=capturing_client,
    ), patch(
        "app.modules.scheduler.upsldc_monitor_service.save_file",
        return_value=str(tmp_path / "vc_first.pdf"),
    ):
        run_monitor(db_session)

    # Second run — same HTML, existing reports
    page_client2 = _make_page_client(_HTML_WITH_VC_REPORTS)
    capturing_client._call_count = 0
    second_pdf_calls: list[str] = []

    def second_client(**kwargs):
        second_client._call_count = getattr(second_client, "_call_count", 0) + 1
        if second_client._call_count == 1:
            return page_client2
        second_pdf_calls.append("pdf_fetch")
        return pdf_client

    with patch(
        "app.modules.scheduler.upsldc_monitor_service.httpx.Client",
        side_effect=second_client,
    ), patch(
        "app.modules.scheduler.upsldc_monitor_service.save_file",
        return_value=str(tmp_path / "vc_second.pdf"),
    ):
        result2 = run_monitor(db_session)

    assert result2.new_report_count == 0
    assert result2.existing_report_count >= 1
    # No PDF downloads on second run for existing reports
    assert len(second_pdf_calls) == 0
    # archived_pdf_count stays at 0 for second run
    assert result2.archived_pdf_count == 0


# ---------------------------------------------------------------------------
# 20. Duplicate PDF hash skipped without re-archiving
# ---------------------------------------------------------------------------

def test_duplicate_pdf_hash_skipped(db_session, tmp_path):
    """If same PDF content exists in documents table, UPSLDC_PDF_DUPLICATE_SKIPPED is emitted."""
    pdf_content = _make_pdf_content()
    from app.modules.documents.storage import compute_sha256
    file_hash = compute_sha256(pdf_content)

    # Pre-create a document with the same hash
    import os

    from app.modules.documents import repository as doc_repo
    os.makedirs(str(tmp_path / "variable_cost_pdf"), exist_ok=True)
    doc_repo.create_document(
        db_session,
        document_type="VARIABLE_COST_PDF",
        original_filename="pre_existing.pdf",
        storage_path=str(tmp_path / "variable_cost_pdf" / "pre_existing.pdf"),
        sha256_hash=file_hash,
        plant_id=None,
        needs_review=True,
        review_status="pending_review",
        notes="pre-existing",
    )
    db_session.commit()

    page_client = _make_page_client(_HTML_WITH_VC_REPORTS)
    pdf_resp = MagicMock()
    pdf_resp.status_code = 200
    pdf_resp.headers = {"content-type": "application/pdf"}
    pdf_resp.content = pdf_content  # same bytes → same hash
    pdf_resp.raise_for_status = lambda: None
    pdf_client = MagicMock()
    pdf_client.__enter__ = lambda s: pdf_client
    pdf_client.__exit__ = MagicMock(return_value=False)
    pdf_client.get = MagicMock(return_value=pdf_resp)

    client_iter = iter([page_client, pdf_client, pdf_client, pdf_client])
    with patch(
        "app.modules.scheduler.upsldc_monitor_service.httpx.Client",
        side_effect=lambda **kw: next(client_iter),
    ), patch(
        "app.modules.scheduler.upsldc_monitor_service.save_file",
        return_value=str(tmp_path / "dup.pdf"),
    ):
        run_monitor(db_session)

    dup_events = db_session.execute(
        select(AuditLog).where(AuditLog.action == "UPSLDC_PDF_DUPLICATE_SKIPPED")
    ).scalars().all()
    assert len(dup_events) >= 1

    # Only the pre-existing doc should exist; no new doc created
    all_docs = db_session.execute(
        select(Document).where(Document.document_type == "VARIABLE_COST_PDF")
    ).scalars().all()
    assert len(all_docs) == 1


# ---------------------------------------------------------------------------
# 21. PDF download failure creates audit event, monitoring row preserved
# ---------------------------------------------------------------------------

def test_pdf_download_failure_audited_monitoring_row_preserved(db_session):
    """PDF download fails → UPSLDC_PDF_DOWNLOAD_FAILED audit, monitor row still exists."""
    page_client = _make_page_client(_HTML_WITH_VC_REPORTS)

    fail_client = MagicMock()
    fail_client.__enter__ = lambda s: fail_client
    fail_client.__exit__ = MagicMock(return_value=False)
    fail_client.get = MagicMock(side_effect=Exception("Connection refused"))

    client_iter = iter([page_client, fail_client, fail_client, fail_client])
    with patch(
        "app.modules.scheduler.upsldc_monitor_service.httpx.Client",
        side_effect=lambda **kw: next(client_iter),
    ):
        result = run_monitor(db_session)

    assert result.new_report_count >= 1
    assert result.archived_pdf_count == 0  # no PDFs archived

    # Monitoring rows still created
    rows = db_session.execute(
        select(UpsldcMonitoredReport)
    ).scalars().all()
    assert len(rows) >= 1

    # Audit failure events created
    fail_events = db_session.execute(
        select(AuditLog).where(AuditLog.action == "UPSLDC_PDF_DOWNLOAD_FAILED")
    ).scalars().all()
    assert len(fail_events) >= 1
    assert fail_events[0].actor_type == "SYSTEM"
    assert fail_events[0].source == "SCHEDULER"


# ---------------------------------------------------------------------------
# 22. PDF content-type mismatch rejected (not archived)
# ---------------------------------------------------------------------------

def test_pdf_wrong_content_type_rejected(db_session, tmp_path):
    """Response with text/html content-type is rejected as invalid PDF."""
    page_client = _make_page_client(_HTML_WITH_VC_REPORTS)

    bad_pdf_resp = MagicMock()
    bad_pdf_resp.status_code = 200
    bad_pdf_resp.headers = {"content-type": "text/html"}  # NOT a PDF
    bad_pdf_resp.content = b"<html>Not a PDF</html>"
    bad_pdf_resp.raise_for_status = lambda: None
    bad_client = MagicMock()
    bad_client.__enter__ = lambda s: bad_client
    bad_client.__exit__ = MagicMock(return_value=False)
    bad_client.get = MagicMock(return_value=bad_pdf_resp)

    client_iter = iter([page_client, bad_client, bad_client, bad_client])
    with patch(
        "app.modules.scheduler.upsldc_monitor_service.httpx.Client",
        side_effect=lambda **kw: next(client_iter),
    ), patch(
        "app.modules.scheduler.upsldc_monitor_service.save_file",
        return_value=str(tmp_path / "bad.pdf"),
    ):
        result = run_monitor(db_session)

    assert result.archived_pdf_count == 0
    docs = db_session.execute(select(Document)).scalars().all()
    assert len(docs) == 0

    fail_events = db_session.execute(
        select(AuditLog).where(AuditLog.action == "UPSLDC_PDF_DOWNLOAD_FAILED")
    ).scalars().all()
    assert len(fail_events) >= 1


# ---------------------------------------------------------------------------
# 23. Oversized PDF rejected (not archived)
# ---------------------------------------------------------------------------

def test_oversized_pdf_rejected(db_session, tmp_path):
    """PDF response larger than max allowed bytes is rejected."""
    page_client = _make_page_client(_HTML_WITH_VC_REPORTS)

    big_content = b"x" * (36 * 1024 * 1024 + 1)  # just over 35 MB
    big_resp = MagicMock()
    big_resp.status_code = 200
    big_resp.headers = {"content-type": "application/pdf"}
    big_resp.content = big_content
    big_resp.raise_for_status = lambda: None
    big_client = MagicMock()
    big_client.__enter__ = lambda s: big_client
    big_client.__exit__ = MagicMock(return_value=False)
    big_client.get = MagicMock(return_value=big_resp)

    client_iter = iter([page_client, big_client, big_client, big_client])
    with patch(
        "app.modules.scheduler.upsldc_monitor_service.httpx.Client",
        side_effect=lambda **kw: next(client_iter),
    ), patch(
        "app.modules.scheduler.upsldc_monitor_service.save_file",
        return_value=str(tmp_path / "big.pdf"),
    ):
        result = run_monitor(db_session)

    assert result.archived_pdf_count == 0
    docs = db_session.execute(select(Document)).scalars().all()
    assert len(docs) == 0
    fail_events = db_session.execute(
        select(AuditLog).where(AuditLog.action == "UPSLDC_PDF_DOWNLOAD_FAILED")
    ).scalars().all()
    assert len(fail_events) >= 1


# ---------------------------------------------------------------------------
# 24. Document record is NOT auto-approved and NOT parsed
# ---------------------------------------------------------------------------

def test_archived_document_not_approved_not_parsed(db_session, tmp_path):
    """Archived document must have needs_review=True and no VariableCost rows."""
    pdf_content = _make_pdf_content()
    page_client = _make_page_client(_HTML_WITH_VC_REPORTS)
    pdf_resp = MagicMock()
    pdf_resp.status_code = 200
    pdf_resp.headers = {"content-type": "application/pdf"}
    pdf_resp.content = pdf_content
    pdf_resp.raise_for_status = lambda: None
    pdf_client = MagicMock()
    pdf_client.__enter__ = lambda s: pdf_client
    pdf_client.__exit__ = MagicMock(return_value=False)
    pdf_client.get = MagicMock(return_value=pdf_resp)

    client_iter = iter([page_client, pdf_client, pdf_client, pdf_client])
    with patch(
        "app.modules.scheduler.upsldc_monitor_service.httpx.Client",
        side_effect=lambda **kw: next(client_iter),
    ), patch(
        "app.modules.scheduler.upsldc_monitor_service.save_file",
        return_value=str(tmp_path / "vc.pdf"),
    ):
        run_monitor(db_session)

    docs = db_session.execute(
        select(Document).where(Document.document_type == "VARIABLE_COST_PDF")
    ).scalars().all()

    for doc in docs:
        assert doc.needs_review is True, "Document must not be auto-approved"
        assert doc.review_status == "pending_review", "Document must stay pending review"

    from app.modules.documents.models import VariableCost
    vc_rows = db_session.execute(select(VariableCost)).scalars().all()
    assert len(vc_rows) == 0, "No VariableCost rows should be created without manual approval"
