import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog


def list_logs(
    db: Session,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    optimization_run_id: uuid.UUID | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    stmt = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)

    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
        count_stmt = count_stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
        count_stmt = count_stmt.where(AuditLog.entity_id == entity_id)
    if document_id:
        stmt = stmt.where(AuditLog.document_id == document_id)
        count_stmt = count_stmt.where(AuditLog.document_id == document_id)
    if optimization_run_id:
        stmt = stmt.where(AuditLog.optimization_run_id == optimization_run_id)
        count_stmt = count_stmt.where(AuditLog.optimization_run_id == optimization_run_id)
    if occurred_from:
        stmt = stmt.where(AuditLog.occurred_at >= occurred_from)
        count_stmt = count_stmt.where(AuditLog.occurred_at >= occurred_from)
    if occurred_to:
        stmt = stmt.where(AuditLog.occurred_at <= occurred_to)
        count_stmt = count_stmt.where(AuditLog.occurred_at <= occurred_to)

    total = db.execute(count_stmt).scalar_one()
    
    # Stable ordering: 1. occurred_at descending, 2. id descending as tie-breaker
    stmt = stmt.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit)
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_log(db: Session, audit_log_id: uuid.UUID) -> AuditLog | None:
    return db.execute(select(AuditLog).where(AuditLog.id == audit_log_id)).scalar_one_or_none()
