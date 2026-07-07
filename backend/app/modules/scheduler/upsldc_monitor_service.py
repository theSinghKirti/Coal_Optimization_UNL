"""UPSLDC MOD Reports monitor service — page monitoring and safe PDF archival.

This module performs:
1. Safe HTTP fetch of the UPSLDC MOD Reports listing page.
2. Extraction of top-N report rows (title + PDF URL).
3. Classification of Variable Cost / Variable Charges reports only.
4. Duplicate-detection against the upsldc_monitored_reports table.
5. Writing of UPSLDC_VARIABLE_COST_REPORT_NEW_DETECTED audit events.
6. For newly detected reports: download the PDF and archive it in local storage.
7. Create Document metadata record with needs_review=True, pending_review status.
8. Audit archival success (UPSLDC_PDF_ARCHIVED) or failure (UPSLDC_PDF_DOWNLOAD_FAILED).

This module does NOT:
- Parse PDF text content or create VariableCost rows.
- Auto-approve or activate any document.
- Trigger optimization or extraction.
- Store raw HTML, cookies, headers, or secrets.
- Download PDFs for already-seen reports.
"""

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.audit import service as audit_service
from app.modules.documents import repository as doc_repository
from app.modules.documents.storage import compute_sha256, save_file
from app.modules.scheduler.monitor_models import UpsldcMonitoredReport

logger = logging.getLogger("codsp.upsldc_monitor")
settings = get_settings()

SOURCE_NAME = "UPSLDC_SCHMOD"
_MAX_PAGE_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB limit for listing page

# PDF content types we accept
_PDF_CONTENT_TYPES = {"application/pdf", "application/octet-stream", "binary/octet-stream"}

# ---------------------------------------------------------------------------
# Keyword matching — exact phrases only, case-insensitive
# ---------------------------------------------------------------------------
_VARIABLE_COST_KEYWORDS = [
    "variable charges",
    "variable charge",
    "variable cost",
    "mod stack of variable charges",
]

# Effective date pattern: dd-mm-yyyy to dd-mm-yyyy
_DATE_RANGE_RE = re.compile(
    r"(\d{1,2}-\d{1,2}-\d{4})\s+to\s+(\d{1,2}-\d{1,2}-\d{4})",
    re.IGNORECASE,
)
_DATE_FMT = "%d-%m-%Y"


# ---------------------------------------------------------------------------
# HTML link extractor (stdlib only — no BeautifulSoup)
# ---------------------------------------------------------------------------
class _PdfLinkExtractor(HTMLParser):
    """Extracts (link_text, href) pairs where href ends with .pdf."""

    def __init__(self, source_url: str) -> None:
        super().__init__()
        self.source_url = source_url
        self.rows: list[tuple[str, str]] = []  # (title, absolute_url)
        self._current_text: list[str] = []
        self._current_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "") or ""
            if href.lower().endswith(".pdf"):
                self._current_href = urljoin(self.source_url, href)
                self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href is not None:
            title = " ".join(self._current_text).strip()
            if not title:
                title = self._current_href.rsplit("/", 1)[-1]
            self.rows.append((title, self._current_href))
            self._current_href = None
            self._current_text = []


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def hash_url(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()


def is_variable_cost_report(title: str) -> bool:
    lower = normalize_title(title)
    return any(kw in lower for kw in _VARIABLE_COST_KEYWORDS)


def parse_effective_dates(title: str) -> tuple[date | None, date | None]:
    """Parse date range from title when the format is unambiguous. Returns (None, None) if uncertain."""
    m = _DATE_RANGE_RE.search(title)
    if not m:
        return None, None
    try:
        d_from = datetime.strptime(m.group(1), _DATE_FMT).date()
        d_to = datetime.strptime(m.group(2), _DATE_FMT).date()
        return d_from, d_to
    except ValueError:
        return None, None


# ---------------------------------------------------------------------------
# Network fetch — listing page
# ---------------------------------------------------------------------------

def fetch_mod_reports_page(
    url: str,
    timeout: int,
    user_agent: str,
) -> str | None:
    """Fetch the MOD Reports listing page HTML. Returns string or None on failure. Never raises."""
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}
    try:
        with httpx.Client(timeout=float(timeout), follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()

            # Content-type validation
            content_type = response.headers.get("content-type", "").lower()
            if "html" not in content_type and "text" not in content_type:
                logger.warning("Unexpected content-type from UPSLDC page: %s", content_type)
                return None

            raw = response.content
            if len(raw) > _MAX_PAGE_RESPONSE_BYTES:
                logger.warning("UPSLDC page response too large (%d bytes), truncating.", len(raw))
                raw = raw[:_MAX_PAGE_RESPONSE_BYTES]

            return raw.decode("utf-8", errors="replace")
    except Exception:
        logger.exception("Failed to fetch UPSLDC MOD Reports page: %s", url)
        return None


# ---------------------------------------------------------------------------
# Network fetch — individual PDF
# ---------------------------------------------------------------------------

def fetch_pdf_bytes(
    url: str,
    timeout: int,
    user_agent: str,
    max_bytes: int,
) -> tuple[bytes | None, str | None]:
    """Download a single PDF. Returns (content_bytes, None) on success or (None, error_msg) on failure.

    Validates:
    - HTTP success status
    - Content-Type is PDF-like
    - Response size within max_bytes

    Never raises.
    """
    headers = {"User-Agent": user_agent, "Accept": "application/pdf,application/octet-stream,*/*"}
    try:
        with httpx.Client(timeout=float(timeout), follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower().split(";")[0].strip()
            # Accept pdf-like types; also accept octet-stream (common for forced PDF downloads)
            if content_type not in _PDF_CONTENT_TYPES and "pdf" not in content_type:
                return None, f"Unexpected content-type '{content_type}' for PDF URL."

            content = response.content
            if len(content) > max_bytes:
                return None, (
                    f"PDF response too large: {len(content)} bytes > max {max_bytes} bytes."
                )
            if len(content) == 0:
                return None, "PDF response was empty."

            return content, None
    except Exception as exc:  # noqa: BLE001
        return None, f"HTTP error fetching PDF: {type(exc).__name__}"


# ---------------------------------------------------------------------------
# PDF archive step — called only for NEW_DETECTED reports
# ---------------------------------------------------------------------------

def _archive_pdf(
    db: Session,
    monitor_entry: UpsldcMonitoredReport,
    run_id: str,
) -> None:
    """Download and archive the PDF for a newly detected report.

    - Skips if document_id is already set (already archived).
    - Checks SHA-256 duplicate against documents table.
    - Creates Document with needs_review=True, review_status='pending_review'.
    - Records UPSLDC_PDF_ARCHIVED or UPSLDC_PDF_DOWNLOAD_FAILED audit event.
    - Never parses PDF content or creates VariableCost rows.
    - Never raises — errors are audited and swallowed.
    """
    pdf_url = monitor_entry.report_url

    # Guard: already archived
    if monitor_entry.document_id is not None:
        logger.info("PDF already archived for report %s, skipping.", monitor_entry.id)
        return

    max_bytes = settings.document_max_upload_size_bytes
    content, error_msg = fetch_pdf_bytes(
        url=pdf_url,
        timeout=settings.upsldc_monitor_timeout_seconds,
        user_agent=settings.upsldc_monitor_user_agent,
        max_bytes=max_bytes,
    )

    if content is None:
        logger.warning("PDF download failed for %s: %s", pdf_url, error_msg)
        audit_service.record(
            db,
            entity_type="upsldc_monitor",
            entity_id=monitor_entry.id,
            action="UPSLDC_PDF_DOWNLOAD_FAILED",
            actor_type="SYSTEM",
            source="SCHEDULER",
            audit_metadata={
                "run_id": run_id,
                "report_url": pdf_url,
                "report_url_hash": monitor_entry.report_url_hash,
                "error": error_msg,
            },
        )
        db.commit()
        return

    # Duplicate check by content hash
    file_hash = compute_sha256(content)
    existing_doc = doc_repository.get_document_by_hash(db, file_hash)
    if existing_doc is not None:
        logger.info("PDF already archived (duplicate hash) for %s. Linking.", pdf_url)
        monitor_entry.document_id = existing_doc.id
        audit_service.record(
            db,
            entity_type="upsldc_monitor",
            entity_id=monitor_entry.id,
            action="UPSLDC_PDF_DUPLICATE_SKIPPED",
            actor_type="SYSTEM",
            source="SCHEDULER",
            audit_metadata={
                "run_id": run_id,
                "report_url": pdf_url,
                "existing_document_id": str(existing_doc.id),
                "sha256_hash": file_hash,
            },
        )
        db.commit()
        return

    # Derive a safe filename from the URL
    filename_part = pdf_url.rsplit("/", 1)[-1].split("?")[0] or "upsldc_variable_cost.pdf"
    if not filename_part.lower().endswith(".pdf"):
        filename_part += ".pdf"

    # Save to git-ignored local storage (storage/documents/variable_cost_pdf/)
    try:
        storage_path = save_file(content, filename_part, subfolder="variable_cost_pdf")
    except Exception:
        logger.exception("Failed to save PDF to local storage for %s", pdf_url)
        audit_service.record(
            db,
            entity_type="upsldc_monitor",
            entity_id=monitor_entry.id,
            action="UPSLDC_PDF_DOWNLOAD_FAILED",
            actor_type="SYSTEM",
            source="SCHEDULER",
            audit_metadata={
                "run_id": run_id,
                "report_url": pdf_url,
                "error": "Local storage write failed.",
            },
        )
        db.commit()
        return

    # Create Document record — pending review, NOT approved, NO extraction
    document = doc_repository.create_document(
        db,
        document_type="VARIABLE_COST_PDF",
        original_filename=filename_part,
        storage_path=storage_path,
        sha256_hash=file_hash,
        plant_id=None,
        needs_review=True,
        review_status="pending_review",
        notes=(
            f"Automatically archived from UPSLDC MOD Reports monitoring. "
            f"Source URL: {pdf_url}. Pending manual review."
        ),
    )

    # Link monitor entry → document
    monitor_entry.document_id = document.id

    # Audit the archival (SYSTEM/SCHEDULER, not API)
    audit_service.record(
        db,
        entity_type="document",
        entity_id=document.id,
        action="UPSLDC_PDF_ARCHIVED",
        document_id=document.id,
        actor_type="SYSTEM",
        source="SCHEDULER",
        after={
            "document_type": "VARIABLE_COST_PDF",
            "original_filename": filename_part,
            "sha256_hash": file_hash,
            "needs_review": True,
            "review_status": "pending_review",
        },
        audit_metadata={
            "run_id": run_id,
            "report_url": pdf_url,
            "report_url_hash": monitor_entry.report_url_hash,
            "report_title": monitor_entry.report_title,
            "size_bytes": len(content),
        },
    )
    db.commit()
    logger.info(
        "PDF archived for '%s' → document_id=%s (pending_review).",
        monitor_entry.report_title,
        document.id,
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_report_rows(html: str, source_url: str, top_n: int) -> list[tuple[str, str]]:
    """Return up to top_n (title, absolute_pdf_url) pairs from the page HTML."""
    extractor = _PdfLinkExtractor(source_url)
    extractor.feed(html)
    return extractor.rows[:top_n]


# ---------------------------------------------------------------------------
# Run result
# ---------------------------------------------------------------------------

@dataclass
class MonitorRunResult:
    source_reachable: bool = True
    scanned_row_count: int = 0
    variable_cost_count: int = 0
    new_report_count: int = 0
    existing_report_count: int = 0
    archived_pdf_count: int = 0
    detected_reports: list[dict] = field(default_factory=list)
    error_safe_message: str | None = None
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_monitor(db: Session) -> MonitorRunResult:
    """Main entry point for one monitoring cycle. Safe — never raises."""
    result = MonitorRunResult()

    # Emit UPSLDC_MONITOR_STARTED
    audit_service.record(
        db,
        entity_type="upsldc_monitor",
        entity_id=None,
        action="UPSLDC_MONITOR_STARTED",
        actor_type="SYSTEM",
        source="SCHEDULER",
        audit_metadata={
            "run_id": result.run_id,
            "source_page_url": settings.upsldc_mod_reports_url,
            "top_n": settings.upsldc_monitor_top_n,
        },
    )
    db.commit()

    try:
        html = fetch_mod_reports_page(
            url=settings.upsldc_mod_reports_url,
            timeout=settings.upsldc_monitor_timeout_seconds,
            user_agent=settings.upsldc_monitor_user_agent,
        )
        if html is None:
            result.source_reachable = False
            result.error_safe_message = (
                "UPSLDC MOD Reports page was unreachable or returned invalid content."
            )
            _emit_monitor_failed(db, result)
            return result

        rows = parse_report_rows(html, settings.upsldc_mod_reports_url, settings.upsldc_monitor_top_n)
        result.scanned_row_count = len(rows)

        for title, pdf_url in rows:
            if not is_variable_cost_report(title):
                continue
            result.variable_cost_count += 1

            url_hash = hash_url(pdf_url)
            eff_from, eff_to = parse_effective_dates(title)
            norm_title = normalize_title(title)

            # Detect new vs existing
            stmt = select(UpsldcMonitoredReport).where(
                UpsldcMonitoredReport.source_name == SOURCE_NAME,
                UpsldcMonitoredReport.report_url_hash == url_hash,
            )
            existing = db.execute(stmt).scalars().first()

            now = datetime.now(UTC)
            report_dict = {
                "title": title,
                "report_url": pdf_url,
                "effective_from": eff_from.isoformat() if eff_from else None,
                "effective_to": eff_to.isoformat() if eff_to else None,
            }

            if existing is None:
                # New report — create monitoring metadata row
                new_entry = UpsldcMonitoredReport(
                    source_name=SOURCE_NAME,
                    source_page_url=settings.upsldc_mod_reports_url,
                    report_title=title,
                    normalized_report_title=norm_title,
                    report_url=pdf_url,
                    report_url_hash=url_hash,
                    report_type="VARIABLE_COST",
                    effective_from=eff_from,
                    effective_to=eff_to,
                    first_seen_at=now,
                    last_seen_at=now,
                    last_check_run_id=result.run_id,
                    is_currently_visible=True,
                    document_id=None,
                )
                db.add(new_entry)
                db.flush()

                # Emit new-detection audit event
                audit_service.record(
                    db,
                    entity_type="upsldc_monitor",
                    entity_id=None,
                    action="UPSLDC_VARIABLE_COST_REPORT_NEW_DETECTED",
                    actor_type="SYSTEM",
                    source="SCHEDULER",
                    audit_metadata={
                        "run_id": result.run_id,
                        "report_title": title,
                        "report_url_hash": url_hash,
                        "effective_from": eff_from.isoformat() if eff_from else None,
                        "effective_to": eff_to.isoformat() if eff_to else None,
                        "source_page_url": settings.upsldc_mod_reports_url,
                    },
                )
                db.commit()

                # Archive the PDF — download, store, create Document record (pending_review)
                _archive_pdf(db, new_entry, result.run_id)
                if new_entry.document_id is not None:
                    result.archived_pdf_count += 1
                    report_dict["document_id"] = str(new_entry.document_id)
                else:
                    report_dict["document_id"] = None

                result.new_report_count += 1
                report_dict["detection_status"] = "NEW_DETECTED"
                report_dict["first_seen_at"] = now.isoformat()
                report_dict["last_seen_at"] = now.isoformat()
            else:
                # Existing — update tracking fields only; no re-download
                existing.last_seen_at = now
                existing.last_check_run_id = result.run_id
                existing.is_currently_visible = True

                result.existing_report_count += 1
                report_dict["detection_status"] = "EXISTING_SEEN"
                report_dict["first_seen_at"] = existing.first_seen_at.isoformat()
                report_dict["last_seen_at"] = now.isoformat()
                report_dict["document_id"] = str(existing.document_id) if existing.document_id else None

            result.detected_reports.append(report_dict)

        db.commit()

        # Emit UPSLDC_MONITOR_COMPLETED
        audit_service.record(
            db,
            entity_type="upsldc_monitor",
            entity_id=None,
            action="UPSLDC_MONITOR_COMPLETED",
            actor_type="SYSTEM",
            source="SCHEDULER",
            audit_metadata={
                "run_id": result.run_id,
                "source_page_url": settings.upsldc_mod_reports_url,
                "scanned_row_count": result.scanned_row_count,
                "variable_cost_count": result.variable_cost_count,
                "new_report_count": result.new_report_count,
                "existing_report_count": result.existing_report_count,
                "archived_pdf_count": result.archived_pdf_count,
            },
        )
        db.commit()

    except Exception:
        logger.exception("UPSLDC monitor run failed unexpectedly.")
        result.source_reachable = False
        result.error_safe_message = "Unexpected error during monitor run. See server logs."
        _emit_monitor_failed(db, result)

    return result


def _emit_monitor_failed(db: Session, result: MonitorRunResult) -> None:
    try:
        audit_service.record(
            db,
            entity_type="upsldc_monitor",
            entity_id=None,
            action="UPSLDC_MONITOR_FAILED",
            actor_type="SYSTEM",
            source="SCHEDULER",
            audit_metadata={
                "run_id": result.run_id,
                "source_page_url": settings.upsldc_mod_reports_url,
                "error": result.error_safe_message,
            },
        )
        db.commit()
    except Exception:
        logger.exception("Failed to write UPSLDC_MONITOR_FAILED audit event.")
