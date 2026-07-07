import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["CRITICAL", "WARNING", "INFO"]
    entity_type: str
    entity_id: uuid.UUID | None = None
    plant_id: uuid.UUID | None = None
    message: str
    suggested_action: str


class ValidationSummary(BaseModel):
    overall_status: Literal["READY", "WARNING", "INCOMPLETE"]
    generated_at: datetime
    as_of_date: date
    total_issues: int
    issues: list[ValidationIssue]

