import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import UUIDPKMixin, utcnow
from app.core.database import Base


class AuditLog(Base, UUIDPKMixin):
    __tablename__ = "audit_logs"

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    optimization_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("optimization_runs.id", ondelete="SET NULL"), nullable=True
    )
    
    before: Mapped[dict | None] = mapped_column("before_state", JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column("after_state", JSON, nullable=True)
    audit_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    
    actor_type: Mapped[str] = mapped_column(String(64), nullable=False, default="SYSTEM")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="SYSTEM")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
