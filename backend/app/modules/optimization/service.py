"""Coal allocation optimization workflow.

Orchestrates: gather inputs -> run the deterministic PuLP/CBC solver ->
persist an auditable run snapshot + allocation results.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.audit import service as audit_service
from app.modules.constraints.models import FSAConstraint
from app.modules.daily_stock import repository as daily_stock_repository
from app.modules.landed_cost.models import LandedCost
from app.modules.master_data.models import Plant
from app.modules.optimization import repository
from app.modules.optimization.models import OptimizationRun
from app.modules.optimization.schemas import OptimizationRunRequest
from app.modules.optimization.solver import ContractSource, PlantDemand, solve
from app.modules.recommendations import service as recommendations_service
from app.modules.validation import service as validation_service
from app.modules.validation.schemas import ValidationIssue

settings = get_settings()


def _monthly_acq_cap(constraint) -> float:
    if constraint.monthly_cap_mt is not None:
        return float(constraint.monthly_cap_mt)
    if constraint.annual_contract_quantity_mt is not None:
        return float(constraint.annual_contract_quantity_mt) * 30 / 365
    return 0.0


def get_eligible_landed_costs(db: Session, plant_id: uuid.UUID, as_of: date) -> list[LandedCost]:
    stmt = select(LandedCost).where(
        LandedCost.plant_id == plant_id,
        LandedCost.status == "APPROVED",
        LandedCost.is_active.is_(True),
        LandedCost.needs_review.is_(False),
        LandedCost.effective_from <= as_of,
        (LandedCost.effective_to.is_(None)) | (LandedCost.effective_to >= as_of),
    )
    return list(db.execute(stmt).scalars().all())


def _resolve_landed_cost_for_source(
    eligible_landed_costs: list[LandedCost], supplier_id: uuid.UUID | None
) -> LandedCost | None:
    if supplier_id:
        matching = [c for c in eligible_landed_costs if c.supplier_id == supplier_id]
        if matching:
            return max(matching, key=lambda c: c.effective_from)
    # fall back to a plant-level (no specific supplier) landed cost record
    plant_level = [c for c in eligible_landed_costs if c.supplier_id is None]
    if plant_level:
        return max(plant_level, key=lambda c: c.effective_from)
    if eligible_landed_costs:
        return max(eligible_landed_costs, key=lambda c: c.effective_from)
    return None


def run_optimization(db: Session, payload: OptimizationRunRequest) -> OptimizationRun:
    as_of = payload.as_of_date or date.today()
    now = datetime.now(UTC)

    # 1. Run Validation Summary logic
    summary = validation_service.generate_summary(db)
    has_critical = any(issue.severity == "CRITICAL" for issue in summary.issues)

    if has_critical:
        # Save run as INCOMPLETE and return
        run = repository.create_run(
            db,
            run_timestamp=now,
            status="INCOMPLETE",
            triggered_by=payload.triggered_by,
            solver_status="validation_failed",
            total_estimated_cost=None,
            notes=payload.notes or "Input validation failed; required operational data is missing.",
            input_snapshot={},
            as_of_date=as_of,
            validation_summary=summary.model_dump(mode="json"),
        )
        db.flush()

        audit_service.record(
            db,
            entity_type="optimization_run",
            entity_id=run.id,
            action="OPTIMIZATION_RUN_REQUESTED",
            optimization_run_id=run.id,
            after={"as_of_date": str(as_of)},
            actor_type="UNAUTHENTICATED_API",
            source="API",
        )

        audit_service.record(
            db,
            entity_type="optimization_run",
            entity_id=run.id,
            action="OPTIMIZATION_RUN_INCOMPLETE",
            optimization_run_id=run.id,
            after={"status": run.status, "solver_status": run.solver_status},
            actor_type="UNAUTHENTICATED_API",
            source="API",
        )
        return run

    # 2. Query active plants
    stmt = select(Plant).where(Plant.is_active.is_(True))
    if payload.plant_ids:
        stmt = stmt.where(Plant.id.in_(payload.plant_ids))
    plants = list(db.execute(stmt).scalars().all())

    demands: list[PlantDemand] = []
    sources: list[ContractSource] = []
    missing_data_notes: list[str] = []
    plant_stock_info: dict[str, dict] = {}
    additional_issues: list[ValidationIssue] = []

    for plant in plants:
        stock_rows, _ = daily_stock_repository.list_records(db, plant_id=plant.id, limit=1, offset=0)
        latest = stock_rows[0] if stock_rows else None

        if latest is None:
            additional_issues.append(
                ValidationIssue(
                    code="MISSING_DAILY_STOCK",
                    severity="CRITICAL",
                    entity_type="daily_stock",
                    entity_id=None,
                    plant_id=plant.id,
                    message=f"No daily stock record has ever been submitted for plant '{plant.plant_code}'.",
                    suggested_action="Upload or enter a daily stock record for this plant.",
                )
            )
            continue

        consumption = float(latest.consumption_mt)
        closing_stock = float(latest.closing_stock_mt)
        monthly_demand = max(0.0, float(30 * consumption - closing_stock))
        stock_days = (closing_stock / consumption) if consumption > 0 else None
        plant_stock_info[str(plant.id)] = {"stock_days": stock_days, "missing_stock": False}

        if monthly_demand <= 0:
            continue

        # Find eligible constraints (APPROVED, active, within validity dates)
        eligible_constraints = []
        for c in db.execute(select(FSAConstraint).where(FSAConstraint.plant_id == plant.id)).scalars().all():
            if c.status == "APPROVED" and c.is_active:
                if c.contract_start_date and c.contract_start_date > as_of:
                    continue
                if c.contract_end_date and c.contract_end_date < as_of:
                    continue
                if c.valid_to and c.valid_to < as_of:
                    continue
                qty = _monthly_acq_cap(c)
                if qty > 0:
                    eligible_constraints.append((c, qty))

        # Get eligible landed costs
        eligible_landed_costs = get_eligible_landed_costs(db, plant.id, as_of)

        plant_sources: list[ContractSource] = []
        for constraint, qty in eligible_constraints:
            landed_cost_record = _resolve_landed_cost_for_source(
                eligible_landed_costs, constraint.supplier_id
            )
            if landed_cost_record is None:
                missing_data_notes.append(
                    f"Plant '{plant.plant_code}': no Landed Cost available for "
                    f"{constraint.constraint_type} constraint {constraint.id}; source excluded."
                )
                continue
            plant_sources.append(
                ContractSource(
                    source_id=str(constraint.id),
                    plant_id=str(plant.id),
                    supplier_id=str(constraint.supplier_id) if constraint.supplier_id else None,
                    monthly_cap_mt=qty,
                    landed_cost_per_mt=float(landed_cost_record.total_landed_cost),
                    constraint_type=constraint.constraint_type,
                )
            )

        if eligible_landed_costs:
            market_topup_cost = max(float(c.total_landed_cost) for c in eligible_landed_costs) * 1.20
        elif settings.optimization_fallback_landed_cost > 0:
            market_topup_cost = settings.optimization_fallback_landed_cost * 1.20
        else:
            additional_issues.append(
                ValidationIssue(
                    code="MISSING_APPROVED_ACTIVE_LANDED_COST",
                    severity="CRITICAL",
                    entity_type="landed_cost",
                    entity_id=None,
                    plant_id=plant.id,
                    message=(
                        f"No approved active Landed Cost record is available "
                        f"for plant '{plant.plant_code}'."
                    ),
                    suggested_action=(
                        "Upload landed cost document or approve a "
                        "pending landed cost for this plant."
                    ),
                )
            )

            continue

        demands.append(
            PlantDemand(
                plant_id=str(plant.id),
                monthly_demand_mt=monthly_demand,
                market_topup_cost_per_mt=market_topup_cost,
            )
        )
        sources.extend(plant_sources)

    # 3. Check for any additional critical issues discovered
    if additional_issues:
        all_issues = summary.issues + additional_issues
        run = repository.create_run(
            db,
            run_timestamp=now,
            status="INCOMPLETE",
            triggered_by=payload.triggered_by,
            solver_status="validation_failed",
            total_estimated_cost=None,
            notes=payload.notes or "Input validation failed; required operational data is missing.",
            input_snapshot={},
            as_of_date=as_of,
            validation_summary={
                "overall_status": "INCOMPLETE",
                "total_issues": len(all_issues),
                "issues": [i.model_dump(mode="json") for i in all_issues],
            },

        )
        db.flush()

        audit_service.record(
            db,
            entity_type="optimization_run",
            entity_id=run.id,
            action="OPTIMIZATION_RUN_REQUESTED",
            optimization_run_id=run.id,
            after={"as_of_date": str(as_of)},
            actor_type="UNAUTHENTICATED_API",
            source="API",
        )

        audit_service.record(
            db,
            entity_type="optimization_run",
            entity_id=run.id,
            action="OPTIMIZATION_RUN_INCOMPLETE",
            optimization_run_id=run.id,
            after={"status": run.status, "solver_status": run.solver_status},
            actor_type="UNAUTHENTICATED_API",
            source="API",
        )
        return run

    if not demands:
        run = repository.create_run(
            db,
            run_timestamp=now,
            status="COMPLETED",
            triggered_by=payload.triggered_by,
            solver_status="no_demand",
            total_estimated_cost=0,
            notes=payload.notes or "No plant currently has a monthly coal shortfall requiring allocation.",
            input_snapshot={"plants_considered": len(plants)},
            as_of_date=as_of,
            validation_summary=summary.model_dump(mode="json"),
        )
        db.flush()

        audit_service.record(
            db,
            entity_type="optimization_run",
            entity_id=run.id,
            action="OPTIMIZATION_RUN_REQUESTED",
            optimization_run_id=run.id,
            after={"as_of_date": str(as_of)},
            actor_type="UNAUTHENTICATED_API",
            source="API",
        )

        audit_service.record(
            db,
            entity_type="optimization_run",
            entity_id=run.id,
            action="OPTIMIZATION_RUN_COMPLETED",
            optimization_run_id=run.id,
            after={"status": run.status, "solver_status": run.solver_status},
            actor_type="UNAUTHENTICATED_API",
            source="API",
        )
        return run

    # 4. Solve the model
    try:
        solve_result = solve(demands, sources)
    except Exception as e:
        run = repository.create_run(
            db,
            run_timestamp=now,
            status="FAILED",
            triggered_by=payload.triggered_by,
            solver_status="solver_error",
            total_estimated_cost=None,
            notes=f"Solver execution failed unexpectedly: {str(e)}",
            input_snapshot={
                "demands": [d.__dict__ for d in demands],
                "source_count": len(sources),
            },
            as_of_date=as_of,
            validation_summary=summary.model_dump(mode="json"),
        )
        db.flush()

        audit_service.record(
            db,
            entity_type="optimization_run",
            entity_id=run.id,
            action="OPTIMIZATION_RUN_REQUESTED",
            optimization_run_id=run.id,
            after={"as_of_date": str(as_of)},
            actor_type="UNAUTHENTICATED_API",
            source="API",
        )

        audit_service.record(
            db,
            entity_type="optimization_run",
            entity_id=run.id,
            action="OPTIMIZATION_RUN_FAILED",
            optimization_run_id=run.id,
            after={"status": run.status, "solver_status": run.solver_status},
            actor_type="UNAUTHENTICATED_API",
            source="API",
        )
        return run

    if solve_result.status == "no_sources":
        status_value = "INCOMPLETE"
        solver_status = "no_sources"
    elif solve_result.status == "optimal":
        status_value = "INCOMPLETE" if missing_data_notes else "COMPLETED"
        solver_status = "optimal"
    else:
        status_value = "FAILED"
        solver_status = solve_result.status

    run = repository.create_run(
        db,
        run_timestamp=now,
        status=status_value,
        triggered_by=payload.triggered_by,
        solver_status=solver_status,
        total_estimated_cost=solve_result.total_estimated_cost if solve_result.status == "optimal" else None,
        notes="; ".join(missing_data_notes) if missing_data_notes else payload.notes,
        input_snapshot={
            "demands": [d.__dict__ for d in demands],
            "source_count": len(sources),
        },
        as_of_date=as_of,
        validation_summary=summary.model_dump(mode="json"),
    )
    db.flush()

    # 5. Persist allocations
    if solve_result.status == "optimal":
        for line in solve_result.allocations:
            fsa_constraint_id = None
            coal_company_id = None
            if line.allocation_type in ("fsa", "bridge_linkage") and line.source_id:
                fsa_constraint_id = uuid.UUID(line.source_id)
                constraint = db.get(FSAConstraint, fsa_constraint_id)
                if constraint:
                    coal_company_id = constraint.coal_company_id

            repository.add_allocation(
                db,
                run_id=run.id,
                plant_id=uuid.UUID(line.plant_id),
                supplier_id=uuid.UUID(line.supplier_id) if line.supplier_id else None,
                allocation_type=line.allocation_type,
                quantity_mt=line.quantity_mt,
                unit_cost=line.unit_cost,
                estimated_cost=line.estimated_cost,
                acq_utilization_pct=line.acq_utilization_pct,
                fsa_constraint_id=fsa_constraint_id,
                coal_company_id=coal_company_id,
            )

    db.flush()

    recommendations_service.generate_for_run(
        db,
        run=run,
        allocations=solve_result.allocations if solve_result.status == "optimal" else [],
        plant_stock_info=plant_stock_info,
        missing_data_notes=missing_data_notes,
    )

    audit_service.record(
        db,
        entity_type="optimization_run",
        entity_id=run.id,
        action="OPTIMIZATION_RUN_REQUESTED",
        optimization_run_id=run.id,
        after={"as_of_date": str(as_of)},
        actor_type="UNAUTHENTICATED_API",
        source="API",
    )

    action_value = f"OPTIMIZATION_RUN_{run.status}"
    audit_service.record(
        db,
        entity_type="optimization_run",
        entity_id=run.id,
        action=action_value,
        optimization_run_id=run.id,
        after={"status": run.status, "solver_status": run.solver_status},
        actor_type="UNAUTHENTICATED_API",
        source="API",
    )
    return run


def get_run_or_404(db: Session, run_id: uuid.UUID) -> OptimizationRun:
    from app.core.exceptions import NotFoundError
    run = repository.get_run(db, run_id)
    if not run:
        raise NotFoundError("Optimization run not found.")
    return run


def list_runs(db: Session, *, limit: int, offset: int):
    return repository.list_runs(db, limit=limit, offset=offset)


def get_latest_run_or_404(db: Session) -> OptimizationRun:
    from app.core.exceptions import NotFoundError
    run = repository.get_latest_run(db)
    if not run:
        raise NotFoundError("No optimization runs have been executed yet.")
    return run
