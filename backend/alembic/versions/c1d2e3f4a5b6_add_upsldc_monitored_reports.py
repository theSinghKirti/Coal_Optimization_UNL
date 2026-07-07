"""add_upsldc_monitored_reports

Revision ID: c1d2e3f4a5b6
Revises: 5220887f6dc5
Create Date: 2026-07-07 07:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "5220887f6dc5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "upsldc_monitored_reports",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source_name", sa.String(64), nullable=False),
        sa.Column("source_page_url", sa.String(512), nullable=False),
        sa.Column("report_title", sa.String(512), nullable=False),
        sa.Column("normalized_report_title", sa.String(512), nullable=False),
        sa.Column("report_url", sa.String(512), nullable=False),
        sa.Column("report_url_hash", sa.String(64), nullable=False),
        sa.Column("report_type", sa.String(32), nullable=False, server_default="OTHER"),
        sa.Column("effective_from", sa.Date, nullable=True),
        sa.Column("effective_to", sa.Date, nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_check_run_id", sa.String(64), nullable=True),
        sa.Column("is_currently_visible", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_name", "report_url_hash", name="uq_upsldc_monitored_source_url_hash"),
    )
    op.create_index(
        "ix_upsldc_monitored_reports_source_name",
        "upsldc_monitored_reports",
        ["source_name"],
    )
    op.create_index(
        "ix_upsldc_monitored_reports_report_url_hash",
        "upsldc_monitored_reports",
        ["report_url_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_upsldc_monitored_reports_report_url_hash", table_name="upsldc_monitored_reports")
    op.drop_index("ix_upsldc_monitored_reports_source_name", table_name="upsldc_monitored_reports")
    op.drop_table("upsldc_monitored_reports")
