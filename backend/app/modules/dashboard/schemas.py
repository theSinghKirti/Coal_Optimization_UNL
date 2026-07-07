import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class DashboardMetadata(BaseModel):
    generated_at: datetime
    as_of_date: date | None = None
    system_status: Literal["READY", "WARNING", "INCOMPLETE"]


class DashboardBlocker(BaseModel):
    code: str
    category: str
    severity: Literal["CRITICAL", "WARNING", "INFO"]
    message: str
    affected_plant_count: int | None = None
    affected_entity_type: str | None = None


class DashboardValidationSnapshot(BaseModel):
    validation_status: Literal["READY", "WARNING", "INCOMPLETE"]
    critical_issue_count: int
    warning_issue_count: int
    total_issue_count: int
    top_blockers: list[DashboardBlocker]


class DashboardOptimizationSnapshot(BaseModel):
    latest_run_exists: bool
    run_id: uuid.UUID | None = None
    run_status: str | None = None
    solver_status: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    validation_status_at_run: str | None = None
    run_message: str | None = None

    # Completed-run metrics (nullable if no run exists or is not COMPLETED)
    plants_covered_count: int | None = None
    total_demand_mt: float | None = None
    total_allocated_mt: float | None = None
    market_top_up_mt: float | None = None
    total_estimated_cost: float | None = None
    allocation_count: int | None = None


class DailyStockCoverage(BaseModel):
    total_active_plants: int
    plants_with_latest_daily_stock: int
    plants_missing_latest_daily_stock: int
    latest_daily_stock_date: date | None = None


class FsaConstraintCoverage(BaseModel):
    approved_active_constraint_count: int
    pending_review_constraint_count: int
    unmapped_constraint_count: int
    rejected_constraint_count: int


class LandedCostCoverage(BaseModel):
    approved_active_landed_cost_count: int
    pending_review_landed_cost_count: int
    needs_review_landed_cost_count: int
    rejected_landed_cost_count: int
    plants_with_approved_landed_cost: int
    plants_missing_approved_landed_cost: int


class VariableCostCoverage(BaseModel):
    available_record_count: int
    pending_review_count: int
    approved_count: int
    latest_effective_date: date | None = None


class DashboardCoverage(BaseModel):
    daily_stock: DailyStockCoverage
    fsa_constraint: FsaConstraintCoverage
    landed_cost: LandedCostCoverage
    variable_cost: VariableCostCoverage


class DashboardNextAction(BaseModel):
    priority: Literal["CRITICAL", "WARNING", "INFO"]
    title: str
    message: str
    related_module: str
    affected_count: int | None = None


class DashboardSummary(BaseModel):
    metadata: DashboardMetadata
    validation: DashboardValidationSnapshot
    optimization: DashboardOptimizationSnapshot
    coverage: DashboardCoverage
    next_actions: list[DashboardNextAction]
