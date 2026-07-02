"""
models.py
All Pydantic request/response models used across the API.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ── Request models ────────────────────────────────────────────────────────────

class OptimizationRequest(BaseModel):
    custom_demands: Optional[Dict[str, float]] = Field(
        None,
        description="Custom demand overrides in MT per plant, e.g. {'Anpara': 1200000.0}"
    )
    market_premium: Optional[float] = Field(
        1.35,
        ge=1.0,
        description="Spot-market cost multiplier applied to shortfall pricing (default 1.35)"
    )


class DailyFuelEntry(BaseModel):
    plant: str
    report_date: str
    fuel_type: str
    monthly_linkage: Optional[float] = None
    opening_balance: Optional[float] = None
    receipt: Optional[float] = None
    consumption_release: Optional[float] = None
    closing_balance: Optional[float] = None
    days_stock_cover: Optional[float] = None
    rakes_received: Optional[int] = None
    generation_mu: Optional[float] = None
    plf_pct: Optional[float] = None
    reconciliation_flag: Optional[bool] = False
    reconciliation_delta: Optional[float] = 0.0


class ConstraintEntry(BaseModel):
    plant: str
    company: str
    linkage_type: str
    acq_lac_mt: float
    valid_to: Optional[str] = None
    source_clause: Optional[str] = None


# ── Response models ───────────────────────────────────────────────────────────

class AllocationRow(BaseModel):
    plant: str
    company: str
    allocated_mt: float
    landed_cost_rs_mt: float
    acq_cap_mt: float
    acq_utilisation_pct: Optional[float]


class ShortfallRow(BaseModel):
    plant: str
    shortfall_mt: float
    assumed_market_rate_rs_mt: float
    note: str


class OptimizationResult(BaseModel):
    status: str
    plants_covered: List[str]
    total_optimized_cost_rs: float
    baseline_cost_rs: float
    estimated_savings_rs: float
    estimated_savings_pct: Optional[float]
    allocations: List[AllocationRow]
    shortfalls: List[ShortfallRow]


class SnapshotResponse(BaseModel):
    optimization: OptimizationResult
    daily_fuel: List[DailyFuelEntry]
    constraints: List[ConstraintEntry]
    generated_from: str
