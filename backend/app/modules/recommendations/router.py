import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.core.database import get_db
from app.modules.recommendations import service
from app.modules.recommendations.schemas import RecommendationLatestSummary, RecommendationRead

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/latest", response_model=RecommendationLatestSummary)
def get_latest_recommendations(db: Session = Depends(get_db)):
    """Generate and retrieve deterministic recommendations based on the current system state."""
    return service.build_latest_recommendations(db)


@router.get("", response_model=Page[RecommendationRead])
def list_recommendations(
    plant_id: uuid.UUID | None = Query(default=None),
    severity: str | None = Query(default=None, pattern="^(info|warning|critical)$"),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    items, total = service.list_recommendations(
        db,
        plant_id=plant_id,
        severity=severity,
        limit=page_params.page_size,
        offset=page_params.offset,
    )
    return Page(items=items, page=page_params.page, page_size=page_params.page_size, total=total)
