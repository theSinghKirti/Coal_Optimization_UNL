"""ORM model for tracking observed UPSLDC MOD report entries.

Stores only safe monitoring metadata — no PDF bytes, no HTML, no secrets.
Uniqueness is enforced via (source_name, report_url_hash) so revised reports
that publish a new PDF URL are correctly treated as new entries.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import TimestampMixin, UUIDPKMixin, utcnow
from app.core.database import Base


class UpsldcMonitoredReport(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "upsldc_monitored_reports"
    __table_args__ = (
        UniqueConstraint("source_name", "report_url_hash", name="uq_upsldc_monitored_source_url_hash"),
    )

    # Source identification
    source_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_page_url: Mapped[str] = mapped_column(String(512), nullable=False)

    # Report identity
    report_title: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_report_title: Mapped[str] = mapped_column(String(512), nullable=False)
    report_url: Mapped[str] = mapped_column(String(512), nullable=False)
    report_url_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Classification
    report_type: Mapped[str] = mapped_column(String(32), nullable=False, default="OTHER")

    # Parsed effective dates (nullable — only set when title format is unambiguous)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Observability timestamps
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    # Run tracking — free-form run identifier from the monitoring job
    last_check_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Visibility flag — True if the report was visible in the most recent monitor run
    is_currently_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Linked document record created after PDF archival (null until PDF is downloaded)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
