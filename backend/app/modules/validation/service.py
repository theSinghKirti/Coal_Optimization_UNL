"""Validation summary: aggregates missing/invalid/expired/warning conditions
across daily stock, Variable Cost, FSA/Bridge Linkage, and Landed Cost data.

This module is read-only: it reports issues, it never mutates data.
"""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.constraints.models import FSAConstraint
from app.modules.daily_stock import repository as daily_stock_repository
from app.modules.documents import repository as documents_repository
from app.modules.documents.models import VariableCost
from app.modules.landed_cost.models import LandedCost
from app.modules.master_data.models import Plant
from app.modules.validation.schemas import ValidationIssue, ValidationSummary


def build_validation_summary(db: Session) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    today = date.today()

    # Get active plants
    active_plants = list(db.execute(select(Plant).where(Plant.is_active.is_(True))).scalars().all())

    # --- 1. Daily Stock Checks ---
    for plant, record in daily_stock_repository.latest_per_active_plant(db):
        if record is None:
            issues.append(
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
        else:
            if record.validation_status == "warning":
                issues.append(
                    ValidationIssue(
                        code="RECONCILIATION_WARNING",
                        severity="WARNING",
                        entity_type="daily_stock",
                        entity_id=record.id,
                        plant_id=plant.id,
                        message=(
                            f"Plant '{plant.plant_code}' has a reconciliation mismatch of "
                            f"{float(record.reconciliation_difference_mt):.3f} MT on {record.report_date}."
                        ),
                        suggested_action=(
                            "Review and reconcile the daily stock records to resolve discrepancy."
                        ),

                    )
                )

    # --- 2. Variable Cost Checks ---
    latest_vc_by_plant = {
        vc.plant_id
        for vc in documents_repository.latest_variable_cost_per_plant(db)
    }
    for plant in active_plants:
        if plant.id not in latest_vc_by_plant:
            issues.append(
                ValidationIssue(
                    code="MISSING_VARIABLE_COST",
                    severity="CRITICAL",
                    entity_type="variable_cost",
                    entity_id=None,
                    plant_id=plant.id,
                    message=f"No approved Variable Cost record is available for plant '{plant.plant_code}'.",
                    suggested_action="Upload variable cost document or approve pending values.",
                )
            )

    pending_vcs = list(
        db.execute(select(VariableCost).where(VariableCost.needs_review.is_(True))).scalars().all()
    )
    for vc in pending_vcs:
        issues.append(
            ValidationIssue(
                code="VARIABLE_COST_NEEDS_REVIEW",
                severity="WARNING",
                entity_type="variable_cost",
                entity_id=vc.id,
                plant_id=vc.plant_id,
                message=f"Variable Cost record for '{vc.source_plant_name}' is pending manual review.",
                suggested_action="Review and approve the pending variable cost entries.",
            )
        )

    # --- 3. FSA / Bridge Checks ---
    constraints = list(db.execute(select(FSAConstraint)).scalars().all())
    plants_with_active_constraint = set()

    for c in constraints:
        if c.plant_id is None:
            issues.append(
                ValidationIssue(
                    code="UNMAPPED_FSA_BRIDGE_CONSTRAINT",
                    severity="CRITICAL",
                    entity_type="fsa_constraint",
                    entity_id=c.id,
                    plant_id=None,
                    message=f"Constraint record {c.id} has no mapped plant.",
                    suggested_action="Map the constraint to a valid plant during manual review.",
                )
            )
            if c.status == "PENDING_REVIEW":
                issues.append(
                    ValidationIssue(
                        code="FSA_BRIDGE_PENDING_REVIEW",
                        severity="WARNING",
                        entity_type="fsa_constraint",
                        entity_id=c.id,
                        plant_id=None,
                        message=f"Constraint record {c.id} is pending manual review.",
                        suggested_action="Review and approve/reject the pending constraint.",
                    )
                )
            continue

        is_expired = c.valid_to is not None and c.valid_to < today
        if c.status == "APPROVED" and c.is_active and not is_expired:
            plants_with_active_constraint.add(c.plant_id)

        if c.status == "PENDING_REVIEW":
            issues.append(
                ValidationIssue(
                    code="FSA_BRIDGE_PENDING_REVIEW",
                    severity="WARNING",
                    entity_type="fsa_constraint",
                    entity_id=c.id,
                    plant_id=c.plant_id,
                    message=f"Constraint for raw source '{c.raw_source_name}' is pending manual review.",
                    suggested_action="Review and approve/reject the pending constraint.",
                )
            )
        elif c.status == "REJECTED":
            issues.append(
                ValidationIssue(
                    code="REJECTED_FSA_BRIDGE_CONSTRAINT",
                    severity="WARNING",
                    entity_type="fsa_constraint",
                    entity_id=c.id,
                    plant_id=c.plant_id,
                    message=f"Historical constraint for raw source '{c.raw_source_name}' is rejected.",
                    suggested_action="Review rejected constraints if they need reactivation.",
                )
            )

        if c.constraint_type == "BRIDGE_LINKAGE" and c.status == "APPROVED" and is_expired:
            issues.append(
                ValidationIssue(
                    code="EXPIRED_BRIDGE_LINKAGE",
                    severity="WARNING",
                    entity_type="fsa_constraint",
                    entity_id=c.id,
                    plant_id=c.plant_id,
                    message=(
                        f"Approved Bridge Linkage constraint for raw source "
                        f"'{c.raw_source_name}' expired on {c.valid_to}."
                    ),
                    suggested_action="Renew or update the bridge linkage constraint dates.",
                )
            )

    for plant in active_plants:
        if plant.id not in plants_with_active_constraint:
            issues.append(
                ValidationIssue(
                    code="MISSING_ACTIVE_FSA_BRIDGE_CONSTRAINT",
                    severity="CRITICAL",
                    entity_type="fsa_constraint",
                    entity_id=None,
                    plant_id=plant.id,
                    message=(
                        f"No approved, active FSA or Bridge Linkage constraint exists "
                        f"for plant '{plant.plant_code}'."
                    ),
                    suggested_action="Configure or approve an active FSA/Bridge constraint for this plant.",
                )
            )

    # --- 4. Landed Cost Checks ---
    landed_costs = list(db.execute(select(LandedCost)).scalars().all())
    plants_with_active_landed_cost = set()

    for lc in landed_costs:
        if lc.plant_id is None:
            if lc.status == "PENDING_REVIEW":
                issues.append(
                    ValidationIssue(
                        code="LANDED_COST_PENDING_REVIEW",
                        severity="WARNING",
                        entity_type="landed_cost",
                        entity_id=lc.id,
                        plant_id=None,
                        message=f"Landed Cost record {lc.id} is pending manual review.",
                        suggested_action="Review and approve/reject the pending landed cost record.",
                    )
                )
            if lc.needs_review:
                issues.append(
                    ValidationIssue(
                        code="LANDED_COST_NEEDS_REVIEW",
                        severity="WARNING",
                        entity_type="landed_cost",
                        entity_id=lc.id,
                        plant_id=None,
                        message=f"Landed Cost record {lc.id} is flagged as needing review.",
                        suggested_action="Resolve the issues and mark needs_review as false.",
                    )
                )
            continue

        is_expired = lc.effective_to is not None and lc.effective_to < today
        is_effective = lc.effective_from is not None and lc.effective_from <= today
        if lc.status == "APPROVED" and lc.is_active and is_effective and not is_expired:
            plants_with_active_landed_cost.add(lc.plant_id)

        if lc.status == "PENDING_REVIEW":
            issues.append(
                ValidationIssue(
                    code="LANDED_COST_PENDING_REVIEW",
                    severity="WARNING",
                    entity_type="landed_cost",
                    entity_id=lc.id,
                    plant_id=lc.plant_id,
                    message=(
                        f"Landed Cost for '{lc.raw_source_name or lc.plant_id}' "
                        f"is pending manual review."
                    ),
                    suggested_action="Review and approve/reject the pending landed cost record.",
                )
            )

        if lc.needs_review:
            issues.append(
                ValidationIssue(
                    code="LANDED_COST_NEEDS_REVIEW",
                    severity="WARNING",
                    entity_type="landed_cost",
                    entity_id=lc.id,
                    plant_id=lc.plant_id,
                    message=(
                        f"Landed Cost for '{lc.raw_source_name or lc.plant_id}' "
                        f"is flagged as needing review."
                    ),
                    suggested_action="Resolve the issues and mark needs_review as false.",
                )
            )

        if lc.status == "REJECTED":
            issues.append(
                ValidationIssue(
                    code="REJECTED_LANDED_COST",
                    severity="WARNING",
                    entity_type="landed_cost",
                    entity_id=lc.id,
                    plant_id=lc.plant_id,
                    message=f"Landed Cost for '{lc.raw_source_name or lc.plant_id}' is rejected.",
                    suggested_action="Review rejected landed cost records.",
                )
            )

    for plant in active_plants:
        if plant.id not in plants_with_active_landed_cost:
            issues.append(
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


    # --- 5. Documents Checks ---
    review_docs, review_total = documents_repository.list_documents(db, needs_review=True, limit=500)
    for doc in review_docs:
        issues.append(
            ValidationIssue(
                code="DOCUMENT_NEEDS_REVIEW",
                severity="WARNING",
                entity_type="document",
                entity_id=doc.id,
                plant_id=doc.plant_id,
                message=(
                    f"Document '{doc.original_filename}' ({doc.document_type}) "
                    f"has extraction issues and needs review."
                ),
                suggested_action="Resolve the manual review flag on the uploaded document.",
            )
        )

    return issues


def generate_summary(db: Session) -> ValidationSummary:
    issues = build_validation_summary(db)

    # Compute overall status
    has_critical = any(issue.severity == "CRITICAL" for issue in issues)
    has_warning = any(issue.severity == "WARNING" for issue in issues)

    if has_critical:
        status = "INCOMPLETE"
    elif has_warning:
        status = "WARNING"
    else:
        status = "READY"

    return ValidationSummary(
        overall_status=status,
        generated_at=datetime.now(UTC),
        as_of_date=date.today(),
        total_issues=len(issues),
        issues=issues,
    )

