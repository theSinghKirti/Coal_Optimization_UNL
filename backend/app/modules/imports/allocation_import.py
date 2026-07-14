"""Allocation result importer — inserts AllocationResult records for a given run.

Expected columns (case-insensitive):
  Required:
    run_id             — UUID of an existing OptimizationRun
    plant_code         — resolved to plant_id
    allocation_type    — one of: fsa, bridge_linkage, market_topup
    quantity_mt        — float > 0
    unit_cost          — float ≥ 0 (Rs/MT)
  Optional:
    supplier_name      — resolved to supplier_id
    fsa_constraint_id  — UUID
    coal_company_id    — UUID

AllocationResult has no unique dedup constraint — allocation rows are per-run.
This importer always inserts; it is the caller's responsibility to avoid
submitting duplicate runs.
"""

from __future__ import annotations

import logging
import uuid

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.imports.base import BaseImporter, ImportResult
from app.modules.master_data.models import Plant, Supplier
from app.modules.optimization.models import AllocationResult, OptimizationRun

logger = logging.getLogger(__name__)

_VALID_ALLOC_TYPES = {"fsa", "bridge_linkage", "market_topup"}


def _resolve_plant(session: Session, code: str) -> Plant | None:
    return session.execute(select(Plant).where(Plant.plant_code == code)).scalar_one_or_none()


def _resolve_supplier(session: Session, name: str | None) -> Supplier | None:
    if not name:
        return None
    return session.execute(select(Supplier).where(Supplier.name.ilike(name.strip()))).scalar_one_or_none()


def _resolve_run(session: Session, run_id_str: str) -> OptimizationRun | None:
    try:
        run_id = uuid.UUID(str(run_id_str).strip())
    except ValueError:
        return None
    return session.execute(select(OptimizationRun).where(OptimizationRun.id == run_id)).scalar_one_or_none()


def _parse_uuid(value) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value).strip())
    except (ValueError, TypeError, AttributeError):
        return None


class AllocationImporter(BaseImporter):
    """Insert AllocationResult rows for a given OptimizationRun."""

    def import_data(self, session: Session, df: pd.DataFrame) -> ImportResult:
        result = ImportResult()
        df = df.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))

        required = ["run_id", "plant_code", "allocation_type", "quantity_mt", "unit_cost"]
        missing = self._require_columns(df, required)
        if missing:
            result.add_error(-1, f"Missing required columns: {missing}")
            return result

        # Cache run lookups to avoid N+1 queries
        run_cache: dict[str, OptimizationRun | None] = {}

        for idx, row in df.iterrows():
            run_id_str = self._str_clean(row.get("run_id"))
            plant_code = self._str_clean(row.get("plant_code"))

            if not run_id_str:
                result.skipped += 1
                result.add_error(int(idx), "run_id is empty — row skipped")
                continue

            if not plant_code:
                result.skipped += 1
                result.add_error(int(idx), "plant_code is empty — row skipped")
                continue

            alloc_type = self._str_clean(row.get("allocation_type")) or ""
            if alloc_type.lower() not in _VALID_ALLOC_TYPES:
                result.skipped += 1
                result.add_error(int(idx), f"allocation_type '{alloc_type}' invalid — must be one of {sorted(_VALID_ALLOC_TYPES)}")
                continue

            quantity = self._parse_float(row.get("quantity_mt"))
            unit_cost = self._parse_float(row.get("unit_cost"))

            if quantity is None or quantity < 0:
                result.skipped += 1
                result.add_error(int(idx), f"quantity_mt invalid for plant '{plant_code}' — row skipped")
                continue

            if unit_cost is None or unit_cost < 0:
                result.skipped += 1
                result.add_error(int(idx), f"unit_cost invalid for plant '{plant_code}' — row skipped")
                continue

            # Resolve run
            if run_id_str not in run_cache:
                run_cache[run_id_str] = _resolve_run(session, run_id_str)
            run = run_cache[run_id_str]
            if run is None:
                result.skipped += 1
                result.add_error(int(idx), f"OptimizationRun '{run_id_str}' not found in DB — row skipped")
                continue

            plant = _resolve_plant(session, plant_code)
            if not plant:
                result.skipped += 1
                result.add_error(int(idx), f"Plant '{plant_code}' not found in DB — row skipped")
                continue

            supplier = _resolve_supplier(session, self._str_clean(row.get("supplier_name")))
            fsa_constraint_id = _parse_uuid(row.get("fsa_constraint_id"))
            coal_company_id = _parse_uuid(row.get("coal_company_id"))
            estimated_cost = quantity * unit_cost

            record = AllocationResult(
                run_id=run.id,
                plant_id=plant.id,
                supplier_id=supplier.id if supplier else None,
                allocation_type=alloc_type.lower(),
                quantity_mt=quantity,  # type: ignore[arg-type]
                unit_cost=unit_cost,  # type: ignore[arg-type]
                estimated_cost=estimated_cost,  # type: ignore[arg-type]
                fsa_constraint_id=fsa_constraint_id,
                coal_company_id=coal_company_id,
            )
            session.add(record)
            session.flush()
            result.inserted += 1

        return result
