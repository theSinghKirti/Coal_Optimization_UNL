import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID | None
    plant_id: uuid.UUID | None
    recommendation_type: str
    severity: str
    message: str
    created_at: datetime


class RecommendationItem(BaseModel):
    recommendation_key: str
    category: Literal[
        "DAILY_STOCK",
        "FSA_BRIDGE",
        "LANDED_COST",
        "VARIABLE_COST",
        "OPTIMIZATION",
        "DATA_QUALITY",
    ]
    severity: Literal["CRITICAL", "WARNING", "INFO"]
    title: str
    message: str
    recommended_next_action: str
    related_module: str
    affected_plant_id: uuid.UUID | None = None
    affected_plant_name: str | None = None
    affected_company: str | None = None
    affected_count: int | None = None
    source_entity_type: str | None = None
    source_entity_ids: list[uuid.UUID] = []
    optimization_run_id: uuid.UUID | None = None
    status_context: str | None = None
    created_from_data_as_of: date | None = None


class RecommendationLatestSummary(BaseModel):
    generated_at: datetime
    system_status: Literal["READY", "WARNING", "INCOMPLETE"]
    recommendation_count: int
    recommendations: list[RecommendationItem]
