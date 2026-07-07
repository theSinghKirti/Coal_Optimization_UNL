"""add_document_id_to_upsldc_monitored_reports

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-07-07 08:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "upsldc_monitored_reports",
        sa.Column(
            "document_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("upsldc_monitored_reports", "document_id")
