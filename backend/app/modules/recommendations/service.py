"""Recommendation generation rules, applied after every optimization run.

Trigger                     | Condition
-----------------------------|---------------------------------------------
Critical Stock                stock days < 1
Low Stock                     stock days < 3
ACQ Near Limit                utilization >= 90%
Market Top-up Required        market top-up quantity > 0
Missing Daily Stock           no recent stock record for an active plant
Missing Variable Cost         no latest VC available
Missing Landed Cost           no active landed cost for required allocation
Optimization Incomplete       required data missing
Optimization Failed           solver failure
"""

import uuid

from sqlalchemy.orm import Session

from app.modules.documents import repository as documents_repository
from app.modules.master_data.models import Plant
from app.modules.optimization.models import OptimizationRun
from app.modules.optimization.solver import AllocationLine
from app.modules.recommendations import repository


def generate_for_run(
    db: Session,
    *,
    run: OptimizationRun,
    allocations: list[AllocationLine],
    plant_stock_info: dict[str, dict],
    missing_data_notes: list[str],
) -> None:
    # Stock-condition recommendations
    for plant_id_str, info in plant_stock_info.items():
        plant_id = uuid.UUID(plant_id_str)
        if info.get("missing_stock"):
            repository.create(
                db,
                run_id=run.id,
                plant_id=plant_id,
                recommendation_type="missing_daily_stock",
                severity="critical",
                message="No recent daily stock record exists for this active plant.",
            )
            continue

        stock_days = info.get("stock_days")
        if stock_days is None:
            continue
        if stock_days < 1:
            repository.create(
                db,
                run_id=run.id,
                plant_id=plant_id,
                recommendation_type="critical_stock",
                severity="critical",
                message=f"Critical stock: only {stock_days:.2f} days of coal remaining.",
            )
        elif stock_days < 3:
            repository.create(
                db,
                run_id=run.id,
                plant_id=plant_id,
                recommendation_type="low_stock",
                severity="warning",
                message=f"Low stock: {stock_days:.2f} days of coal remaining.",
            )

    # ACQ near-limit + market top-up recommendations from allocation results
    for line in allocations:
        if line.acq_utilization_pct is not None and line.acq_utilization_pct >= 90:
            repository.create(
                db,
                run_id=run.id,
                plant_id=uuid.UUID(line.plant_id),
                recommendation_type="acq_near_limit",
                severity="warning",
                message=f"ACQ utilization at {line.acq_utilization_pct:.1f}% for this contract source.",
            )
        if line.allocation_type == "market_topup" and line.quantity_mt > 0:
            repository.create(
                db,
                run_id=run.id,
                plant_id=uuid.UUID(line.plant_id),
                recommendation_type="market_topup_required",
                severity="warning",
                message=f"Market/e-auction top-up of {line.quantity_mt:.2f} MT is required to meet demand.",
            )

    # Missing Variable Cost (dashboard/reporting context, not used in the objective)
    plants = db.query(Plant).filter(Plant.is_active.is_(True)).all()
    latest_vc_plant_ids = {vc.plant_id for vc in documents_repository.latest_variable_cost_per_plant(db)}
    for plant in plants:
        if plant.id not in latest_vc_plant_ids:
            repository.create(
                db,
                run_id=run.id,
                plant_id=plant.id,
                recommendation_type="missing_variable_cost",
                severity="warning",
                message="No approved Variable Cost record is available for operational reporting.",
            )

    # Missing-data / run-level recommendations
    for note in missing_data_notes:
        if "Landed Cost" in note:
            rec_type = "missing_landed_cost"
        else:
            rec_type = "optimization_incomplete"
        repository.create(
            db,
            run_id=run.id,
            plant_id=None,
            recommendation_type=rec_type,
            severity="warning",
            message=note,
        )

    if run.status in ("failed", "FAILED"):
        repository.create(
            db,
            run_id=run.id,
            plant_id=None,
            recommendation_type="optimization_failed",
            severity="critical",
            message=f"Solver could not find a feasible allocation (status: {run.solver_status}).",
        )
    elif run.status in ("incomplete_data", "INCOMPLETE") and not missing_data_notes:
        repository.create(
            db,
            run_id=run.id,
            plant_id=None,
            recommendation_type="optimization_incomplete",
            severity="warning",
            message="Optimization completed with incomplete input data.",
        )



def list_recommendations(db: Session, **filters):
    return repository.list_recommendations(db, **filters)


def build_latest_recommendations(db: Session):
    from datetime import UTC, date, datetime

    from sqlalchemy import select

    from app.modules.constraints.models import FSAConstraint
    from app.modules.daily_stock import repository as daily_stock_repository
    from app.modules.documents.models import VariableCost
    from app.modules.landed_cost.models import LandedCost
    from app.modules.master_data.models import Plant
    from app.modules.optimization import repository as optimization_repository
    from app.modules.recommendations.schemas import (
        RecommendationItem,
        RecommendationLatestSummary,
    )
    from app.modules.validation import service as validation_service

    today = date.today()
    now_time = datetime.now(UTC)

    # 1. Validation summary to retrieve overall status and issues
    val_summary = validation_service.generate_summary(db)
    system_status = val_summary.overall_status

    recommendations: list[RecommendationItem] = []

    # Get active plants
    active_plants = list(db.execute(select(Plant).where(Plant.is_active.is_(True))).scalars().all())
    active_plant_names = {p.id: p.plant_name for p in active_plants}

    # A. Missing Daily Stock
    latest_stock_rows = daily_stock_repository.latest_per_active_plant(db)
    missing_stock_plant_ids = []
    for _plant, record in latest_stock_rows:
        if record is None:
            missing_stock_plant_ids.append(_plant.id)
            
    if missing_stock_plant_ids:
        recommendations.append(
            RecommendationItem(
                recommendation_key="DAILY_STOCK_MISSING_ACTIVE_PLANTS",
                category="DAILY_STOCK",
                severity="CRITICAL",
                title="Latest daily stock is missing",
                message=f"Daily stock records are missing for {len(missing_stock_plant_ids)} active plants.",
                recommended_next_action="Enter latest COAL daily stock for missing plants",
                related_module="daily_stock",
                affected_count=len(missing_stock_plant_ids),
                source_entity_type="plant",
                source_entity_ids=missing_stock_plant_ids,
            )
        )

    # B. Pending or Unmapped FSA / Bridge Constraints
    constraints = list(db.execute(select(FSAConstraint)).scalars().all())
    for c in constraints:
        if c.plant_id is None:
            recommendations.append(
                RecommendationItem(
                    recommendation_key=f"FSA_BRIDGE_UNMAPPED_CONSTRAINT_{c.id}",
                    category="FSA_BRIDGE",
                    severity="CRITICAL",
                    title="Constraint record requires plant mapping",
                    message=f"Constraint record for raw source '{c.raw_source_name}' has no mapped plant.",
                    recommended_next_action="Map the constraint to a valid plant during manual review.",
                    related_module="fsa_constraint",
                    source_entity_type="fsa_constraint",
                    source_entity_ids=[c.id],
                )
            )
            continue
            
        if c.status == "PENDING_REVIEW":
            recommendations.append(
                RecommendationItem(
                    recommendation_key=f"FSA_BRIDGE_PENDING_REVIEW_{c.id}",
                    category="FSA_BRIDGE",
                    severity="WARNING",
                    title="FSA/Bridge constraint pending review",
                    message=f"Constraint for raw source '{c.raw_source_name}' is pending manual review.",
                    recommended_next_action="Review and approve/reject the pending constraint.",
                    related_module="fsa_constraint",
                    affected_plant_id=c.plant_id,
                    affected_plant_name=active_plant_names.get(c.plant_id),
                    affected_company=c.coal_company,
                    source_entity_type="fsa_constraint",
                    source_entity_ids=[c.id],
                )
            )
        elif c.status == "REJECTED":
            recommendations.append(
                RecommendationItem(
                    recommendation_key=f"FSA_BRIDGE_REJECTED_CONSTRAINT_{c.id}",
                    category="FSA_BRIDGE",
                    severity="WARNING",
                    title="Rejected FSA/Bridge constraint",
                    message=f"Historical constraint for raw source '{c.raw_source_name}' is rejected.",
                    recommended_next_action="Review rejected constraints if they need reactivation.",
                    related_module="fsa_constraint",
                    affected_plant_id=c.plant_id,
                    affected_plant_name=active_plant_names.get(c.plant_id),
                    source_entity_type="fsa_constraint",
                    source_entity_ids=[c.id],
                )
            )
        elif c.status == "APPROVED" and c.is_active:
            is_expired = c.valid_to is not None and c.valid_to < today
            if is_expired:
                recommendations.append(
                    RecommendationItem(
                        recommendation_key=f"FSA_BRIDGE_EXPIRED_CONSTRAINT_{c.id}",
                        category="FSA_BRIDGE",
                        severity="WARNING",
                        title="Expired Bridge Linkage constraint",
                        message=(
                            f"Approved Bridge Linkage constraint for raw source "
                            f"'{c.raw_source_name}' expired on {c.valid_to}."
                        ),
                        recommended_next_action="Renew or update the bridge linkage constraint dates.",
                        related_module="fsa_constraint",
                        affected_plant_id=c.plant_id,
                        affected_plant_name=active_plant_names.get(c.plant_id),
                        source_entity_type="fsa_constraint",
                        source_entity_ids=[c.id],
                    )
                )

    # C. Pending / Needs-Review Landed Cost
    landed_costs = list(db.execute(select(LandedCost)).scalars().all())
    plants_with_active_lc = set()
    for lc in landed_costs:
        if lc.status == "PENDING_REVIEW":
            recommendations.append(
                RecommendationItem(
                    recommendation_key=f"LANDED_COST_PENDING_REVIEW_{lc.id}",
                    category="LANDED_COST",
                    severity="WARNING",
                    title="Landed cost pending review",
                    message=(
                        f"Landed Cost for '{lc.raw_source_name or lc.plant_id}' "
                        f"is pending manual review."
                    ),
                    recommended_next_action="Review and approve/reject the pending landed cost record.",
                    related_module="landed_cost",
                    affected_plant_id=lc.plant_id,
                    affected_plant_name=active_plant_names.get(lc.plant_id) if lc.plant_id else None,
                    source_entity_type="landed_cost",
                    source_entity_ids=[lc.id],
                )
            )
        if lc.needs_review:
            recommendations.append(
                RecommendationItem(
                    recommendation_key=f"LANDED_COST_NEEDS_REVIEW_{lc.id}",
                    category="LANDED_COST",
                    severity="WARNING",
                    title="Landed cost needs review",
                    message=(
                        f"Landed Cost for '{lc.raw_source_name or lc.plant_id}' "
                        f"is flagged as needing review."
                    ),
                    recommended_next_action="Resolve the issues and mark needs_review as false.",
                    related_module="landed_cost",
                    affected_plant_id=lc.plant_id,
                    affected_plant_name=active_plant_names.get(lc.plant_id) if lc.plant_id else None,
                    source_entity_type="landed_cost",
                    source_entity_ids=[lc.id],
                )
            )
        if lc.status == "REJECTED":
            recommendations.append(
                RecommendationItem(
                    recommendation_key=f"LANDED_COST_REJECTED_{lc.id}",
                    category="LANDED_COST",
                    severity="WARNING",
                    title="Rejected landed cost record",
                    message=f"Landed Cost for '{lc.raw_source_name or lc.plant_id}' is rejected.",
                    recommended_next_action="Review rejected landed cost records.",
                    related_module="landed_cost",
                    affected_plant_id=lc.plant_id,
                    affected_plant_name=active_plant_names.get(lc.plant_id) if lc.plant_id else None,
                    source_entity_type="landed_cost",
                    source_entity_ids=[lc.id],
                )
            )
        if lc.status == "APPROVED" and lc.is_active:
            is_expired = lc.effective_to is not None and lc.effective_to < today
            is_effective = lc.effective_from is not None and lc.effective_from <= today
            if is_effective and not is_expired:
                if lc.plant_id:
                    plants_with_active_lc.add(lc.plant_id)

    missing_lc_plants = [p for p in active_plants if p.id not in plants_with_active_lc]
    for p in missing_lc_plants:
        recommendations.append(
            RecommendationItem(
                recommendation_key=f"LANDED_COST_MISSING_COVERAGE_{p.id}",
                category="LANDED_COST",
                severity="CRITICAL",
                title="Missing approved active Landed Cost",
                message=f"No approved active Landed Cost record is available for plant '{p.plant_code}'.",
                recommended_next_action=(
                    "Upload landed cost document or approve "
                    "a pending landed cost for this plant."
                ),
                related_module="landed_cost",
                affected_plant_id=p.id,
                affected_plant_name=p.plant_name,
                source_entity_type="plant",
                source_entity_ids=[p.id],
            )
        )

    # D. Variable Cost
    variable_costs = list(db.execute(select(VariableCost)).scalars().all())
    plants_with_vc = set()
    for vc in variable_costs:
        if vc.needs_review:
            recommendations.append(
                RecommendationItem(
                    recommendation_key=f"VARIABLE_COST_NEEDS_REVIEW_{vc.id}",
                    category="VARIABLE_COST",
                    severity="WARNING",
                    title="Variable cost record needs review",
                    message=f"Variable Cost record for '{vc.source_plant_name}' is pending manual review.",
                    recommended_next_action="Review and approve the pending variable cost entries.",
                    related_module="variable_cost",
                    affected_plant_id=vc.plant_id,
                    affected_plant_name=active_plant_names.get(vc.plant_id) if vc.plant_id else None,
                    source_entity_type="variable_cost",
                    source_entity_ids=[vc.id],
                )
            )
        if not vc.needs_review and vc.plant_id is not None:
            plants_with_vc.add(vc.plant_id)

    missing_vc_plants = [p for p in active_plants if p.id not in plants_with_vc]
    for p in missing_vc_plants:
        recommendations.append(
            RecommendationItem(
                recommendation_key=f"VARIABLE_COST_MISSING_COVERAGE_{p.id}",
                category="VARIABLE_COST",
                severity="CRITICAL",
                title="Missing approved active Variable Cost",
                message=f"No approved Variable Cost record is available for plant '{p.plant_code}'.",
                recommended_next_action="Upload variable cost document or approve pending values.",
                related_module="variable_cost",
                affected_plant_id=p.id,
                affected_plant_name=p.plant_name,
                source_entity_type="plant",
                source_entity_ids=[p.id],
            )
        )

    # E. Optimization Incomplete / No Run / Completed Run
    latest_run = optimization_repository.get_latest_run(db)
    if latest_run is None:
        if system_status == "READY" and len(active_plants) > 0:
            recommendations.append(
                RecommendationItem(
                    recommendation_key="OPTIMIZATION_READY",
                    category="OPTIMIZATION",
                    severity="INFO",
                    title="Ready to run optimization",
                    message="All operational inputs are fully validated and ready for solver execution.",
                    recommended_next_action="Execute optimization solver to generate coal allocations.",
                    related_module="optimization",
                )
            )
    elif latest_run.status == "INCOMPLETE":
        recommendations.append(
            RecommendationItem(
                recommendation_key=f"OPTIMIZATION_INCOMPLETE_{latest_run.id}",
                category="OPTIMIZATION",
                severity="CRITICAL",
                title="Latest optimization run incomplete",
                message="Solver cannot produce valid allocation until critical data blockers are resolved.",
                recommended_next_action="Resolve all critical validation blockers and re-run optimization.",
                related_module="optimization",
                optimization_run_id=latest_run.id,
                source_entity_type="optimization_run",
                source_entity_ids=[latest_run.id],
            )
        )
    elif latest_run.status == "COMPLETED":
        for alloc in latest_run.allocations:
            if alloc.allocation_type == "market_topup" and alloc.quantity_mt > 0:
                recommendations.append(
                    RecommendationItem(
                        recommendation_key=f"OPTIMIZATION_MARKET_TOPUP_{alloc.id}",
                        category="OPTIMIZATION",
                        severity="WARNING",
                        title="Market top-up required",
                        message=(
                            f"Market/e-auction top-up of {alloc.quantity_mt:.2f} MT "
                            f"is required to meet demand for plant."
                        ),
                        recommended_next_action=(
                            "Plan procurement of e-auction "
                            "or market coal to fill demand."
                        ),
                        related_module="optimization",
                        affected_plant_id=alloc.plant_id,
                        affected_plant_name=active_plant_names.get(alloc.plant_id),
                        source_entity_type="allocation_result",
                        source_entity_ids=[alloc.id],
                        optimization_run_id=latest_run.id,
                    )
                )
            if alloc.acq_utilization_pct is not None and alloc.acq_utilization_pct >= 90:
                recommendations.append(
                    RecommendationItem(
                        recommendation_key=f"OPTIMIZATION_CONSTRAINT_HIGH_UTILIZATION_{alloc.id}",
                        category="OPTIMIZATION",
                        severity="WARNING",
                        title="ACQ near utilization limit",
                        message=f"Contract source ACQ utilization is at {alloc.acq_utilization_pct:.1f}%.",
                        recommended_next_action="Monitor remaining contract balance for this coal source.",
                        related_module="optimization",
                        affected_plant_id=alloc.plant_id,
                        affected_plant_name=active_plant_names.get(alloc.plant_id),
                        source_entity_type="allocation_result",
                        source_entity_ids=[alloc.id],
                        optimization_run_id=latest_run.id,
                    )
                )

    # Priority and Ordering Rules
    severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    recommendations.sort(
        key=lambda r: (severity_order.get(r.severity, 3), r.category, r.recommendation_key)
    )

    return RecommendationLatestSummary(
        generated_at=now_time,
        system_status=system_status,
        recommendation_count=len(recommendations),
        recommendations=recommendations,
    )
