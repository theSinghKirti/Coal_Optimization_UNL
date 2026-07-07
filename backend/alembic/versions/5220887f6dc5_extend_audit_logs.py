"""extend_audit_logs

Revision ID: 5220887f6dc5
Revises: a8b9c0d1e2f7
Create Date: 2026-07-07 04:10:02.303156

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5220887f6dc5'
down_revision: str | None = 'a8b9c0d1e2f7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column('audit_logs', 'before', new_column_name='before_state')
    op.alter_column('audit_logs', 'after', new_column_name='after_state')
    op.drop_column('audit_logs', 'note')
    op.add_column('audit_logs', sa.Column('metadata', sa.JSON(), nullable=True))
    op.drop_column('audit_logs', 'actor')
    op.add_column(
        'audit_logs',
        sa.Column('actor_type', sa.String(length=64), nullable=False, server_default='SYSTEM')
    )
    op.add_column(
        'audit_logs',
        sa.Column('source', sa.String(length=32), nullable=False, server_default='SYSTEM')
    )
    op.add_column(
        'audit_logs',
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'))
    )
    op.add_column('audit_logs', sa.Column('document_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_audit_logs_document_id', 'audit_logs', 'documents', ['document_id'], ['id'], ondelete='SET NULL'
    )
    op.add_column('audit_logs', sa.Column('optimization_run_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_audit_logs_optimization_run_id',
        'audit_logs',
        'optimization_runs',
        ['optimization_run_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_audit_logs_optimization_run_id', 'audit_logs', type_='foreignkey')
    op.drop_column('audit_logs', 'optimization_run_id')
    op.drop_constraint('fk_audit_logs_document_id', 'audit_logs', type_='foreignkey')
    op.drop_column('audit_logs', 'document_id')
    op.drop_column('audit_logs', 'occurred_at')
    op.drop_column('audit_logs', 'source')
    op.drop_column('audit_logs', 'actor_type')
    op.add_column(
        'audit_logs',
        sa.Column('actor', sa.String(length=64), nullable=False, server_default='system')
    )
    op.drop_column('audit_logs', 'metadata')
    op.add_column('audit_logs', sa.Column('note', sa.String(length=500), nullable=True))
    op.alter_column('audit_logs', 'after_state', new_column_name='after')
    op.alter_column('audit_logs', 'before_state', new_column_name='before')
