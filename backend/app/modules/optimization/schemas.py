import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.modules.validation.schemas import ValidationIssue

RunStatus = Literal["completed", "incomplete_data", "failed", "COMPLETED", "INCOMPLETE", "FAILED"]
TriggerSource = Literal["manual", "scheduler"]


class OptimizationRunRequest(BaseModel):
    triggered_by: TriggerSource = "manual"
    plant_ids: list[uuid.UUID] | None = None  # None = all active plants
    as_of_date: date | None = None
    notes: str | None = None


class AllocationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    plant_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    allocation_type: str
    quantity_mt: float
    unit_cost: float
    estimated_cost: float
    acq_utilization_pct: float | None = None

    # New fields
    fsa_constraint_id: uuid.UUID | None = None
    coal_company_id: uuid.UUID | None = None
    created_at: datetime | None = None

    # Aliases
    optimization_run_id: uuid.UUID | None = None
    allocated_quantity_mt: float | None = None
    landed_cost_rs_per_mt: float | None = None
    estimated_cost_rs: float | None = None
    acq_utilization_percent: float | None = None

    @model_validator(mode="after")
    def populate_aliases(self) -> "AllocationResultRead":
        self.optimization_run_id = self.run_id
        self.allocated_quantity_mt = self.quantity_mt
        self.landed_cost_rs_per_mt = self.unit_cost
        self.estimated_cost_rs = self.estimated_cost
        self.acq_utilization_percent = self.acq_utilization_pct
        return self


class OptimizationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_timestamp: datetime
    status: str
    triggered_by: str
    solver_status: str | None = None
    total_estimated_cost: float | None = None
    notes: str | None = None

    # New fields
    as_of_date: date | None = None
    validation_summary: dict | None = None
    input_snapshot: dict | None = None
    created_at: datetime | None = None

    # Aliases
    run_at: datetime | None = None
    total_estimated_cost_rs: float | None = None

    @model_validator(mode="after")
    def populate_aliases(self) -> "OptimizationRunRead":
        self.run_at = self.run_timestamp
        self.total_estimated_cost_rs = self.total_estimated_cost
        return self


class OptimizationRunDetail(OptimizationRunRead):
    allocations: list[AllocationResultRead]


class OptimizationRunResponse(BaseModel):
    run_id: uuid.UUID
    status: Literal["COMPLETED", "INCOMPLETE", "FAILED"]
    solver_status: str | None = None
    total_estimated_cost_rs: float | None = None
    allocation_count: int
    market_topup_required: bool
    validation_issues: list[ValidationIssue]
    message: str | None = None
