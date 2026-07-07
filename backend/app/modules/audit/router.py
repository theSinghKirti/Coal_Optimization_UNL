import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.modules.audit import repository
from app.modules.audit.schemas import AuditLogPage, AuditLogRead

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get(
    "",
    response_model=AuditLogPage,
    summary="List audit logs",
    description=(
        "Fetch a list of backend audit logs with optional filters "
        "(action, entity_type, entity_id, document_id, optimization_run_id, "
        "occurred_from, occurred_to) and pagination."
    )
)
def list_audit_logs(
    action: str | None = Query(default=None, description="Filter by audit action name (exact match)"),
    entity_type: str | None = Query(default=None, description="Filter by target entity type name"),
    entity_id: uuid.UUID | None = Query(default=None, description="Filter by target entity UUID"),
    document_id: uuid.UUID | None = Query(default=None, description="Filter by associated document UUID"),
    optimization_run_id: uuid.UUID | None = Query(
        default=None, description="Filter by associated optimization run UUID"
    ),
    occurred_from: datetime | None = Query(
        default=None, description="Start date/time for audit records (UTC)"
    ),
    occurred_to: datetime | None = Query(default=None, description="End date/time for audit records (UTC)"),
    page: int = Query(default=1, ge=1, description="1-indexed page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page (max 100)"),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * page_size
    items, total = repository.list_logs(
        db,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        document_id=document_id,
        optimization_run_id=optimization_run_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        limit=page_size,
        offset=offset,
    )
    
    has_next_page = total > (page * page_size)
    
    return AuditLogPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next_page=has_next_page,
    )


@router.get(
    "/{audit_log_id}",
    response_model=AuditLogRead,
    summary="Get audit log detail",
    description="Fetch a single audit log record by its unique UUID."
)
def get_audit_log(
    audit_log_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    log = repository.get_log(db, audit_log_id)
    if not log:
        raise NotFoundError("Audit log not found")
    return log
