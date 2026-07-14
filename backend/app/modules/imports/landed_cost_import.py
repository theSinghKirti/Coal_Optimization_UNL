"""Landed cost importer — upserts LandedCost records from variable-cost spreadsheets.

The Variable Cost workbooks contain per-plant landed cost data:
  ``Coal Cost as per Flexi Matrix April 2026.xlsx``
  ``VC for last 5 months for UNL and IPPs.xlsx``

Normalised CSV/Excel upload columns (case-insensitive):
  Required:
    plant_name          — resolved to plant_id
    total_landed_cost   — Rs/MT
  Optional:
    supplier_name       — resolved to supplier_id
    basic_cost          — Rs/MT (coal basic rate)
    freight             — Rs/MT
    taxes               — Rs/MT (premiums, levies)
    other_cost          — Rs/MT, default 0
    gcv_kcal_per_kg     — Gross Calorific Value
    effective_from      — date (ISO / DD-MM-YYYY)
    effective_to        — date (ISO / DD-MM-YYYY)
    cost_basis          — string, default "CERTIFIED_WEIGHTED_AVERAGE"
    raw_source_name     — source filename
    is_active           — bool, default True

No unique constraint exists on LandedCost in the DB.
Dedup check: existing ACTIVE record with same (plant_id, supplier_id, effective_from).
  - If found → update cost fields.
  - Otherwise → insert.

The workbook parser for the native Flexi Matrix format is also provided here.
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.imports.base import BaseImporter, ImportResult
from app.modules.landed_cost.models import LandedCost
from app.modules.master_data.models import Plant, Supplier

logger = logging.getLogger(__name__)


def _resolve_plant(session: Session, name: str | None) -> Plant | None:
    if not name:
        return None
    p = session.execute(select(Plant).where(Plant.plant_name.ilike(name.strip()))).scalar_one_or_none()
    if p:
        return p
    return session.execute(select(Plant).where(Plant.plant_code.ilike(name.strip()))).scalar_one_or_none()


def _resolve_supplier(session: Session, name: str | None) -> Supplier | None:
    if not name:
        return None
    return session.execute(select(Supplier).where(Supplier.name.ilike(name.strip()))).scalar_one_or_none()


class LandedCostImporter(BaseImporter):
    """Upsert LandedCost records from a normalised DataFrame."""

    def import_data(self, session: Session, df: pd.DataFrame) -> ImportResult:
        result = ImportResult()
        df = df.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))

        missing = self._require_columns(df, ["plant_name", "total_landed_cost"])
        if missing:
            result.add_error(-1, f"Missing required columns: {missing}")
            return result

        for idx, row in df.iterrows():
            plant_name = self._str_clean(row.get("plant_name"))
            if not plant_name:
                result.skipped += 1
                result.add_error(int(idx), "plant_name is empty — row skipped")
                continue

            total_lc = self._parse_float(row.get("total_landed_cost"))
            if total_lc is None or total_lc <= 0:
                result.skipped += 1
                result.add_error(int(idx), f"total_landed_cost invalid for plant '{plant_name}' — row skipped")
                continue

            plant = _resolve_plant(session, plant_name)
            if not plant:
                result.skipped += 1
                result.add_error(int(idx), f"Plant '{plant_name}' not found in DB — skipped")
                continue

            supplier_name = self._str_clean(row.get("supplier_name") or row.get("coal_company"))
            supplier = _resolve_supplier(session, supplier_name)
            supplier_id = supplier.id if supplier else None

            basic_cost = self._parse_float(row.get("basic_cost"))
            freight = self._parse_float(row.get("freight"))
            taxes = self._parse_float(row.get("taxes"))
            other_cost = self._parse_float(row.get("other_cost")) or 0.0
            gcv = self._parse_float(row.get("gcv_kcal_per_kg") or row.get("gcv"))
            effective_from = self._parse_date(row.get("effective_from"))
            effective_to = self._parse_date(row.get("effective_to"))
            raw_source = self._str_clean(row.get("raw_source_name"))
            cost_basis = self._str_clean(row.get("cost_basis")) or "CERTIFIED_WEIGHTED_AVERAGE"
            is_active = True
            is_active_raw = row.get("is_active")
            if is_active_raw is not None and str(is_active_raw).strip().lower() in ("false", "0", "no"):
                is_active = False

            # Compute total if components provided
            if basic_cost is not None and freight is not None:
                computed_total = basic_cost + freight + (taxes or 0.0) + other_cost
            else:
                computed_total = total_lc

            # Dedup: existing active record for same plant/supplier/effective_from
            query = select(LandedCost).where(
                LandedCost.plant_id == plant.id,
                LandedCost.is_active == True,  # noqa: E712
            )
            if supplier_id:
                query = query.where(LandedCost.supplier_id == supplier_id)
            if effective_from:
                query = query.where(LandedCost.effective_from == effective_from)

            existing: LandedCost | None = session.execute(query).scalar_one_or_none()

            if existing:
                existing.basic_cost = basic_cost  # type: ignore[assignment]
                existing.freight = freight  # type: ignore[assignment]
                existing.taxes = taxes  # type: ignore[assignment]
                existing.other_cost = other_cost  # type: ignore[assignment]
                existing.total_landed_cost = computed_total  # type: ignore[assignment]
                existing.weighted_avg_gcv_kcal_per_kg = gcv  # type: ignore[assignment]
                existing.effective_to = effective_to  # type: ignore[assignment]
                existing.raw_source_name = raw_source
                existing.cost_basis = cost_basis
                existing.is_active = is_active
                session.flush()
                result.updated += 1
            else:
                record = LandedCost(
                    plant_id=plant.id,
                    supplier_id=supplier_id,
                    basic_cost=basic_cost,  # type: ignore[arg-type]
                    freight=freight,  # type: ignore[arg-type]
                    taxes=taxes,  # type: ignore[arg-type]
                    other_cost=other_cost,  # type: ignore[arg-type]
                    total_landed_cost=computed_total,  # type: ignore[arg-type]
                    weighted_avg_gcv_kcal_per_kg=gcv,  # type: ignore[arg-type]
                    effective_from=effective_from,  # type: ignore[arg-type]
                    effective_to=effective_to,  # type: ignore[arg-type]
                    raw_source_name=raw_source,
                    cost_basis=cost_basis,
                    is_active=is_active,
                    status="APPROVED",
                    needs_review=False,
                )
                session.add(record)
                session.flush()
                result.inserted += 1

        return result


# ---------------------------------------------------------------------------
# Flexi Matrix workbook parser — extracts landed cost rows
# ---------------------------------------------------------------------------

def parse_variable_cost_workbook(file_bytes: bytes, sheet_name: str | int = 0) -> pd.DataFrame:
    """Parse the 'Coal Cost as per Flexi Matrix' workbook into normalised rows.

    Detects the header row (containing 'TPS' and 'Landed Cost') and extracts:
      plant_name, coal_company (supplier_name), basic_cost, freight,
      total_landed_cost, gcv_kcal_per_kg

    Returns a normalised DataFrame suitable for LandedCostImporter.
    """
    import io
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    if isinstance(sheet_name, int):
        ws = wb.worksheets[sheet_name]
    else:
        ws = wb[sheet_name]

    rows = list(ws.iter_rows(values_only=True))

    # Find header row
    header_idx = None
    header_map: dict[str, int] = {}
    for i, row in enumerate(rows):
        cells = [str(c).strip().lower() if c else "" for c in row]
        if "tps" in cells and any("landed" in c for c in cells):
            header_idx = i
            for j, c in enumerate(cells):
                header_map[c] = j
            break

    if header_idx is None:
        raise ValueError("Could not find header row (TPS + Landed Cost columns) in workbook.")

    def _col(name_fragment: str) -> int | None:
        for k, v in header_map.items():
            if name_fragment in k:
                return v
        return None

    col_tps = _col("tps")
    col_company = _col("coal company") or _col("name of coal")
    col_basic = _col("rate of coal")
    col_freight = _col("freight rate") or _col("freight")
    col_landed = _col("landed cost")
    col_gcv = _col("gcv")

    if col_tps is None or col_landed is None:
        raise ValueError("Could not locate required columns (TPS, Landed Cost) in workbook.")

    records = []
    current_plant = None

    for row in rows[header_idx + 1:]:
        if all(c is None for c in row):
            continue

        def _cell(col: int | None):
            if col is None or col >= len(row):
                return None
            return row[col]

        tps = _cell(col_tps)
        if tps and str(tps).strip():
            tps_str = str(tps).strip().rstrip("*").strip()
            if tps_str and "total" not in tps_str.lower():
                current_plant = tps_str

        if current_plant is None:
            continue

        company_val = _cell(col_company)
        if not company_val or str(company_val).strip() == "":
            continue

        try:
            basic_raw = float(_cell(col_basic)) if _cell(col_basic) else None
        except (TypeError, ValueError):
            basic_raw = None

        try:
            freight_raw = float(_cell(col_freight)) if _cell(col_freight) else None
        except (TypeError, ValueError):
            freight_raw = None

        try:
            landed_raw = float(_cell(col_landed)) if _cell(col_landed) else None
        except (TypeError, ValueError):
            landed_raw = None

        if landed_raw is None:
            if basic_raw is not None and freight_raw is not None:
                landed_raw = basic_raw + freight_raw
            else:
                continue

        try:
            gcv_raw = float(_cell(col_gcv)) if _cell(col_gcv) else None
        except (TypeError, ValueError):
            gcv_raw = None

        records.append({
            "plant_name": current_plant,
            "supplier_name": str(company_val).strip(),
            "basic_cost": basic_raw,
            "freight": freight_raw,
            "total_landed_cost": landed_raw,
            "gcv_kcal_per_kg": gcv_raw,
        })

    return pd.DataFrame(records)
