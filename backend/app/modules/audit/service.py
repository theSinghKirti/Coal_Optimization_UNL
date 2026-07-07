"""Audit logging helper used by every other module.

Every write path that mutates business data or runs optimization should call
`record` so the platform keeps a complete, queryable history of changes.
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog


def record(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID | None,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
    document_id: uuid.UUID | None = None,
    optimization_run_id: uuid.UUID | None = None,
    actor_type: str = "SYSTEM",
    source: str = "SYSTEM",
    audit_metadata: dict | None = None,
    occurred_at: datetime | None = None,
    # Backward-compatible parameters for legacy callers
    actor: str | None = None,
    note: str | None = None,
) -> AuditLog:
    if actor and actor.lower() != "system":
        actor_type = "UNAUTHENTICATED_API"
        source = "API"

    meta = audit_metadata or {}
    if note:
        meta["note"] = note

    log = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        document_id=document_id,
        optimization_run_id=optimization_run_id,
        before=before,
        after=after,
        audit_metadata=meta or None,
        actor_type=actor_type,
        source=source,
    )
    if occurred_at:
        log.occurred_at = occurred_at

    db.add(log)
    return log
