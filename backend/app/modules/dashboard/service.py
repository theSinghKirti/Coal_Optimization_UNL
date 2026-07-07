from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.constraints.models import FSAConstraint
from app.modules.daily_stock import repository as daily_stock_repository
from app.modules.dashboard.schemas import (
    DailyStockCoverage,
    DashboardBlocker,
    DashboardCoverage,
    DashboardMetadata,
    DashboardNextAction,
    DashboardOptimizationSnapshot,
    DashboardSummary,
    DashboardValidationSnapshot,
    FsaConstraintCoverage,
    LandedCostCoverage,
    VariableCostCoverage,
)
from app.modules.documents.models import VariableCost
from app.modules.landed_cost.models import LandedCost
from app.modules.master_data.models import Plant
from app.modules.optimization import repository as optimization_repository
from app.modules.validation import service as validation_service


def build_dashboard_summary(db: Session) -> DashboardSummary:
    today = date.today()
    now_time = datetime.now(UTC)

    # 1. Validation summary
    summary = validation_service.generate_summary(db)
    critical_count = sum(1 for issue in summary.issues if issue.severity == "CRITICAL")
    warning_count = sum(1 for issue in summary.issues if issue.severity == "WARNING")

    # Limit top blockers to 5
    blockers = []
    for issue in summary.issues[:5]:
        blockers.append(
            DashboardBlocker(
                code=issue.code,
                category=issue.entity_type,
                severity=issue.severity,
                message=issue.message,
                affected_plant_count=1 if issue.plant_id else None,
                affected_entity_type=issue.entity_type,
            )
        )

    val_snapshot = DashboardValidationSnapshot(
        validation_status=summary.overall_status,
        critical_issue_count=critical_count,
        warning_issue_count=warning_count,
        total_issue_count=len(summary.issues),
        top_blockers=blockers,
    )

    # 2. Metadata
    metadata = DashboardMetadata(
        generated_at=now_time,
        as_of_date=summary.as_of_date,
        system_status=summary.overall_status,
    )

    # 3. Latest Optimization Run
    latest_run = optimization_repository.get_latest_run(db)
    if latest_run:
        latest_run_exists = True
        run_id = latest_run.id
        run_status = latest_run.status
        solver_status = latest_run.solver_status
        created_at = latest_run.run_timestamp
        completed_at = latest_run.created_at
        
        val_status_run = None
        if latest_run.validation_summary and isinstance(latest_run.validation_summary, dict):
            val_status_run = latest_run.validation_summary.get("overall_status")
        validation_status_at_run = val_status_run
        
        run_message = latest_run.notes
        
        if latest_run.status == "COMPLETED":
            plants_covered = {alloc.plant_id for alloc in latest_run.allocations}
            plants_covered_count = len(plants_covered)
            
            total_demand_mt = 0.0
            if latest_run.input_snapshot and isinstance(latest_run.input_snapshot, dict):
                demands_list = latest_run.input_snapshot.get("demands", [])
                total_demand_mt = sum(float(d.get("monthly_demand_mt", 0.0)) for d in demands_list)
            
            total_allocated_mt = sum(float(alloc.quantity_mt) for alloc in latest_run.allocations)
            
            market_top_up_mt = sum(
                float(alloc.quantity_mt)
                for alloc in latest_run.allocations
                if alloc.allocation_type == "market_topup"
            )
            
            total_estimated_cost = (
                float(latest_run.total_estimated_cost)
                if latest_run.total_estimated_cost is not None
                else None
            )
            allocation_count = len(latest_run.allocations)
        else:
            plants_covered_count = None
            total_demand_mt = None
            total_allocated_mt = None
            market_top_up_mt = None
            total_estimated_cost = None
            allocation_count = None
    else:
        latest_run_exists = False
        run_id = None
        run_status = None
        solver_status = None
        created_at = None
        completed_at = None
        validation_status_at_run = None
        run_message = None
        plants_covered_count = None
        total_demand_mt = None
        total_allocated_mt = None
        market_top_up_mt = None
        total_estimated_cost = None
        allocation_count = None

    opt_snapshot = DashboardOptimizationSnapshot(
        latest_run_exists=latest_run_exists,
        run_id=run_id,
        run_status=run_status,
        solver_status=solver_status,
        created_at=created_at,
        completed_at=completed_at,
        validation_status_at_run=validation_status_at_run,
        run_message=run_message,
        plants_covered_count=plants_covered_count,
        total_demand_mt=total_demand_mt,
        total_allocated_mt=total_allocated_mt,
        market_top_up_mt=market_top_up_mt,
        total_estimated_cost=total_estimated_cost,
        allocation_count=allocation_count,
    )

    # 4. Coverage Metrics
    # Active plants
    active_plants = list(db.execute(select(Plant).where(Plant.is_active.is_(True))).scalars().all())
    total_active_plants = len(active_plants)
    active_plant_ids = {p.id for p in active_plants}

    # Daily Stock
    latest_stock_rows = daily_stock_repository.latest_per_active_plant(db)
    plants_with_latest_daily_stock = 0
    plants_missing_latest_daily_stock = 0
    stock_dates = []
    
    for _plant, record in latest_stock_rows:
        if record is None:
            plants_missing_latest_daily_stock += 1
        else:
            plants_with_latest_daily_stock += 1
            if record.report_date:
                stock_dates.append(record.report_date)
                
    latest_daily_stock_date = max(stock_dates) if stock_dates else None
    
    daily_stock_cov = DailyStockCoverage(
        total_active_plants=total_active_plants,
        plants_with_latest_daily_stock=plants_with_latest_daily_stock,
        plants_missing_latest_daily_stock=plants_missing_latest_daily_stock,
        latest_daily_stock_date=latest_daily_stock_date,
    )

    # FSA / Bridge
    constraints = list(db.execute(select(FSAConstraint)).scalars().all())
    approved_active_constraint_count = 0
    pending_review_constraint_count = 0
    unmapped_constraint_count = 0
    rejected_constraint_count = 0
    
    for c in constraints:
        if c.plant_id is None:
            unmapped_constraint_count += 1
        if c.status == "PENDING_REVIEW":
            pending_review_constraint_count += 1
        elif c.status == "REJECTED":
            rejected_constraint_count += 1
        elif c.status == "APPROVED" and c.is_active:
            is_expired = c.valid_to is not None and c.valid_to < today
            if not is_expired:
                approved_active_constraint_count += 1
                
    fsa_cov = FsaConstraintCoverage(
        approved_active_constraint_count=approved_active_constraint_count,
        pending_review_constraint_count=pending_review_constraint_count,
        unmapped_constraint_count=unmapped_constraint_count,
        rejected_constraint_count=rejected_constraint_count,
    )

    # Landed Cost
    landed_costs = list(db.execute(select(LandedCost)).scalars().all())
    approved_active_landed_cost_count = 0
    pending_review_landed_cost_count = 0
    needs_review_landed_cost_count = 0
    rejected_landed_cost_count = 0
    plants_with_approved_lc = set()
    
    for lc in landed_costs:
        if lc.status == "PENDING_REVIEW":
            pending_review_landed_cost_count += 1
        elif lc.status == "REJECTED":
            rejected_landed_cost_count += 1
        elif lc.status == "APPROVED" and lc.is_active:
            is_expired = lc.effective_to is not None and lc.effective_to < today
            is_effective = lc.effective_from is not None and lc.effective_from <= today
            if is_effective and not is_expired:
                approved_active_landed_cost_count += 1
                if lc.plant_id:
                    plants_with_approved_lc.add(lc.plant_id)
                    
        if lc.needs_review:
            needs_review_landed_cost_count += 1
            
    plants_with_approved_landed_cost = len(plants_with_approved_lc.intersection(active_plant_ids))
    plants_missing_approved_landed_cost = total_active_plants - plants_with_approved_landed_cost
    
    landed_cost_cov = LandedCostCoverage(
        approved_active_landed_cost_count=approved_active_landed_cost_count,
        pending_review_landed_cost_count=pending_review_landed_cost_count,
        needs_review_landed_cost_count=needs_review_landed_cost_count,
        rejected_landed_cost_count=rejected_landed_cost_count,
        plants_with_approved_landed_cost=plants_with_approved_landed_cost,
        plants_missing_approved_landed_cost=plants_missing_approved_landed_cost,
    )

    # Variable Cost
    variable_costs = list(db.execute(select(VariableCost)).scalars().all())
    available_record_count = len(variable_costs)
    pending_review_vc_count = sum(1 for vc in variable_costs if vc.needs_review)
    approved_vc_count = sum(1 for vc in variable_costs if not vc.needs_review and vc.plant_id is not None)
    
    vc_dates = [vc.effective_date for vc in variable_costs if vc.effective_date]
    latest_effective_date = max(vc_dates) if vc_dates else None
    
    variable_cost_cov = VariableCostCoverage(
        available_record_count=available_record_count,
        pending_review_count=pending_review_vc_count,
        approved_count=approved_vc_count,
        latest_effective_date=latest_effective_date,
    )

    coverage = DashboardCoverage(
        daily_stock=daily_stock_cov,
        fsa_constraint=fsa_cov,
        landed_cost=landed_cost_cov,
        variable_cost=variable_cost_cov,
    )

    # 5. Next Actions
    next_actions = []
    
    if plants_missing_latest_daily_stock > 0:
        next_actions.append(
            DashboardNextAction(
                priority="CRITICAL",
                title="Enter latest daily stock",
                message=(
                    f"Daily stock records are missing for "
                    f"{plants_missing_latest_daily_stock} active plants."
                ),
                related_module="daily_stock",
                affected_count=plants_missing_latest_daily_stock,
            )
        )
        
    if pending_review_constraint_count > 0 or unmapped_constraint_count > 0:
        total_fsa_issues = pending_review_constraint_count + unmapped_constraint_count
        next_actions.append(
            DashboardNextAction(
                priority="CRITICAL" if unmapped_constraint_count > 0 else "WARNING",
                title="Review and map pending constraints",
                message=(
                    f"FSA/Bridge constraint records need resolution "
                    f"({pending_review_constraint_count} pending, {unmapped_constraint_count} unmapped)."
                ),
                related_module="fsa_constraint",
                affected_count=total_fsa_issues,
            )
        )
        
    if pending_review_landed_cost_count > 0 or needs_review_landed_cost_count > 0:
        total_lc_issues = pending_review_landed_cost_count + needs_review_landed_cost_count
        next_actions.append(
            DashboardNextAction(
                priority="WARNING",
                title="Approve landed-cost records",
                message=(
                    f"Landed cost records need manual review or approval "
                    f"({pending_review_landed_cost_count} pending, "
                    f"{needs_review_landed_cost_count} needs review)."
                ),
                related_module="landed_cost",
                affected_count=total_lc_issues,
            )
        )
        
    if val_snapshot.validation_status == "INCOMPLETE":
        next_actions.append(
            DashboardNextAction(
                priority="CRITICAL",
                title="Resolve validation blockers",
                message="Resolve all CRITICAL issues before executing the optimization solver.",
                related_module="optimization",
            )
        )
    else:
        next_actions.append(
            DashboardNextAction(
                priority="INFO",
                title="Ready for Optimization",
                message="All input validations passed. You can execute optimization solver.",
                related_module="optimization",
            )
        )

    return DashboardSummary(
        metadata=metadata,
        validation=val_snapshot,
        optimization=opt_snapshot,
        coverage=coverage,
        next_actions=next_actions,
    )
