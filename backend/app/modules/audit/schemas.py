import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    document_id: uuid.UUID | None
    optimization_run_id: uuid.UUID | None
    actor_type: str
    source: str
    occurred_at: datetime
    before_state: dict | None = Field(validation_alias="before")
    after_state: dict | None = Field(validation_alias="after")
    metadata: dict | None = Field(validation_alias="audit_metadata")

    @model_validator(mode="after")
    def redact_sensitive_data(self) -> "AuditLogRead":
        sensitive_keys = {
            "password", "secret", "jwt", "token", "auth", "authorization",
            "header", "headers", "env", "bytes", "file_bytes", "pdf_text",
            "text", "request", "body", "stack_trace", "traceback", "connection"
        }
        
        def _sanitize(d: dict | None) -> dict | None:
            if d is None:
                return None
            sanitized = {}
            for k, v in d.items():
                k_lower = k.lower()
                if any(sk in k_lower for sk in sensitive_keys):
                    continue
                if isinstance(v, dict):
                    sanitized[k] = _sanitize(v)
                elif isinstance(v, list):
                    sanitized[k] = [
                        _sanitize(item) if isinstance(item, dict) else item
                        for item in v
                    ]
                else:
                    sanitized[k] = v
            return sanitized

        self.before_state = _sanitize(self.before_state)
        self.after_state = _sanitize(self.after_state)
        self.metadata = _sanitize(self.metadata)
        return self


class AuditLogPage(BaseModel):
    items: list[AuditLogRead]
    total: int
    page: int
    page_size: int
    has_next_page: bool
