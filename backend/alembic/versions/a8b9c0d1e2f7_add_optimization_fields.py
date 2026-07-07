"""add_optimization_fields

Revision ID: a8b9c0d1e2f7
Revises: f7a8b9c0d1e2
Create Date: 2026-07-06 15:02:10.123456

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'a8b9c0d1e2f7'
down_revision: str | None = 'f7a8b9c0d1e2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add fields to optimization_runs
    op.add_column('optimization_runs', sa.Column('as_of_date', sa.Date(), nullable=True))
    op.add_column('optimization_runs', sa.Column('validation_summary', sa.JSON(), nullable=True))
    op.add_column(
        'optimization_runs',
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )
    op.add_column(
        'optimization_runs',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )

    # 2. Add fields to allocation_results
    op.add_column('allocation_results', sa.Column('fsa_constraint_id', sa.UUID(), nullable=True))
    op.add_column('allocation_results', sa.Column('coal_company_id', sa.UUID(), nullable=True))
    op.add_column(
        'allocation_results',
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )
    op.add_column(
        'allocation_results',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )

    # Foreign Keys
    op.create_foreign_key(
        'fk_alloc_fsa_constraint_id',
        'allocation_results',
        'fsa_constraints',
        ['fsa_constraint_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_alloc_coal_company_id',
        'allocation_results',
        'coal_companies',
        ['coal_company_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_alloc_coal_company_id', 'allocation_results', type_='foreignkey')
    op.drop_constraint('fk_alloc_fsa_constraint_id', 'allocation_results', type_='foreignkey')
    op.drop_column('allocation_results', 'updated_at')
    op.drop_column('allocation_results', 'created_at')
    op.drop_column('allocation_results', 'coal_company_id')
    op.drop_column('allocation_results', 'fsa_constraint_id')
    op.drop_column('optimization_runs', 'updated_at')
    op.drop_column('optimization_runs', 'created_at')
    op.drop_column('optimization_runs', 'validation_summary')
    op.drop_column('optimization_runs', 'as_of_date')
