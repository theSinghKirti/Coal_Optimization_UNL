"""FSA/Bridge Linkage constraint importer.

Reads the structured FSA spreadsheet and upserts FSAConstraint records.

The FSA workbook (``FSA and Bridge Linkage Details 2026-27.xlsx``) has two
logical sections in a single sheet:

  Columns A-C: FSA data
    Plant | Coal Company | ACQ (Lac MT)

  Columns D-G: Bridge Linkage data
    Plant | Coal Company | Bridge Linkage Qty (Lac MT) | Remarks

This importer can also accept a normalised CSV/Excel with these columns:
    plant_name, coal_company, quantity_lac_mt, constraint_type,
    fiscal_year, remarks, valid_to

Dedup key: (plant_id, coal_company_id, constraint_type, fiscal_year)
  - If an identical key exists → update quantity and remarks.
  - Otherwise → insert.

If plant_name or coal_company cannot be resolved to a DB record the row is
logged as a warning and skipped (not counted as an error per se).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.constraints.models import FSAConstraint
from app.modules.imports.base import BaseImporter, ImportResult
from app.modules.master_data.models import CoalCompany, Plant

logger = logging.getLogger(__name__)

_FSA_FISCAL_YEAR = "2026-27"  # Extracted from the known filename context


def _parse_valid_to(remarks: str | None) -> date | None:
    """Extract a date from a remarks string like 'Valid till 12.08.2026'."""
    if not remarks:
        return None
    pattern = r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})"
    m = re.search(pattern, remarks)
    if m:
        try:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date(year, month, day)
        except ValueError:
            return None
    return None


def _resolve_plant(session: Session, name: str | None) -> Plant | None:
    if not name:
        return None
    plant = session.execute(
        select(Plant).where(Plant.plant_name.ilike(name.strip()))
    ).scalar_one_or_none()
    if plant:
        return plant
    plant = session.execute(
        select(Plant).where(Plant.plant_code.ilike(name.strip()))
    ).scalar_one_or_none()
    return plant


def _resolve_company(session: Session, name: str | None) -> CoalCompany | None:
    if not name:
        return None
    return session.execute(
        select(CoalCompany).where(CoalCompany.name.ilike(name.strip()))
    ).scalar_one_or_none()


def _is_summary_row(plant_name: str | None) -> bool:
    """Skip aggregate/total rows that appear in the workbook."""
    if not plant_name:
        return True
    lower = plant_name.lower().strip()
    return any(kw in lower for kw in ("total", "sum", "grand", "flexi"))


class FSAConstraintImporter(BaseImporter):
    """Upsert FSAConstraint records from a normalised DataFrame.

    Expected columns (normalised names after rename):
      plant_name, coal_company, quantity_lac_mt, constraint_type,
      fiscal_year (optional), remarks (optional), valid_to (optional)
    """

    def import_data(self, session: Session, df: pd.DataFrame) -> ImportResult:
        result = ImportResult()
        df = df.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))

        missing = self._require_columns(df, ["plant_name", "coal_company", "quantity_lac_mt"])
        if missing:
            result.add_error(-1, f"Missing required columns: {missing}")
            return result

        for idx, row in df.iterrows():
            plant_name = self._str_clean(row.get("plant_name"))
            company_name = self._str_clean(row.get("coal_company"))
            qty_raw = self._parse_float(row.get("quantity_lac_mt"))
            constraint_type = self._str_clean(row.get("constraint_type")) or "FSA"
            fiscal_year = self._str_clean(row.get("fiscal_year")) or _FSA_FISCAL_YEAR
            remarks = self._str_clean(row.get("remarks"))

            if _is_summary_row(plant_name):
                result.skipped += 1
                logger.debug("Skipping summary row %d: '%s'", idx, plant_name)
                continue

            if not plant_name:
                result.skipped += 1
                result.add_error(int(idx), "plant_name is empty — row skipped")
                continue

            if not company_name:
                result.skipped += 1
                result.add_error(int(idx), f"coal_company is empty for plant '{plant_name}' — row skipped")
                continue

            if qty_raw is None or qty_raw < 0:
                result.skipped += 1
                result.add_error(int(idx), f"quantity_lac_mt invalid for '{plant_name}/{company_name}' — row skipped")
                continue

            if constraint_type not in ("FSA", "BRIDGE_LINKAGE"):
                result.skipped += 1
                result.add_error(int(idx), f"constraint_type '{constraint_type}' is invalid — must be FSA or BRIDGE_LINKAGE")
                continue

            plant = _resolve_plant(session, plant_name)
            if not plant:
                result.skipped += 1
                logger.warning(
                    "Row %d: plant '%s' not found in DB — skipped (insert plant first)",
                    idx, plant_name,
                )
                result.add_error(int(idx), f"Plant '{plant_name}' not found — skipped")
                continue

            company = _resolve_company(session, company_name)
            if not company:
                result.skipped += 1
                logger.warning(
                    "Row %d: coal company '%s' not found in DB — skipped (insert company first)",
                    idx, company_name,
                )
                result.add_error(int(idx), f"CoalCompany '{company_name}' not found — skipped")
                continue

            valid_to = self._parse_date(row.get("valid_to")) or _parse_valid_to(remarks)
            qty_mt = qty_raw * 100_000  # Convert Lac MT → MT

            # Dedup lookup
            existing: FSAConstraint | None = session.execute(
                select(FSAConstraint).where(
                    FSAConstraint.plant_id == plant.id,
                    FSAConstraint.coal_company_id == company.id,
                    FSAConstraint.constraint_type == constraint_type,
                    FSAConstraint.fiscal_year == fiscal_year,
                )
            ).scalar_one_or_none()

            if existing:
                existing.quantity_lac_mt = qty_raw
                existing.quantity_mt = qty_mt
                existing.remarks = remarks
                existing.valid_to = valid_to
                existing.raw_source_name = company_name
                session.flush()
                result.updated += 1
            else:
                record = FSAConstraint(
                    constraint_type=constraint_type,
                    plant_id=plant.id,
                    coal_company_id=company.id,
                    coal_company=company_name,
                    fiscal_year=fiscal_year,
                    quantity_lac_mt=qty_raw,
                    quantity_mt=qty_mt,
                    annual_contract_quantity_mt=qty_mt,
                    valid_to=valid_to,
                    remarks=remarks,
                    raw_source_name=company_name,
                    status="APPROVED",
                    is_active=True,
                )
                session.add(record)
                session.flush()
                result.inserted += 1

        return result


# ---------------------------------------------------------------------------
# FSA Workbook parser — converts the native two-section layout to normalised rows
# ---------------------------------------------------------------------------

def parse_fsa_workbook(file_bytes: bytes) -> pd.DataFrame:
    """Parse the FSA and Bridge Linkage Excel workbook into a normalised DataFrame.

    The workbook has a fixed two-column-group layout:
      Cols A-C: FSA section  (Plant, Coal Company, ACQ Lac MT)
      Cols D-G: Bridge Linkage section (Plant, Coal Company, Qty Lac MT, Remarks)

    Returns a DataFrame with columns:
      plant_name, coal_company, quantity_lac_mt, constraint_type, fiscal_year, remarks
    """
    import io
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))

    # Detect the header row (contains "Plant" and "Coal Company")
    header_row_idx = None
    for i, row in enumerate(rows):
        cells = [str(c).strip() if c else "" for c in row]
        if any("plant" in c.lower() for c in cells) and any("coal" in c.lower() for c in cells):
            header_row_idx = i
            break

    if header_row_idx is None:
        raise ValueError("Could not detect header row in FSA workbook.")

    fiscal_year = _FSA_FISCAL_YEAR
    # Try to infer fiscal year from first non-empty cell
    for row in rows[:4]:
        for cell in row:
            if cell and "202" in str(cell):
                m = re.search(r"(\d{4}-\d{2,4})", str(cell))
                if m:
                    fiscal_year = m.group(1)
                    break

    records = []
    for row in rows[header_row_idx + 1:]:
        # FSA section: cols 0, 1, 2
        fsa_plant = str(row[0]).strip() if row[0] else None
        fsa_company = str(row[1]).strip() if row[1] else None
        fsa_qty = row[2]

        # Bridge Linkage section: cols 3, 4, 5, 6
        bl_plant = str(row[3]).strip() if len(row) > 3 and row[3] else None
        bl_company = str(row[4]).strip() if len(row) > 4 and row[4] else None
        bl_qty = row[5] if len(row) > 5 else None
        bl_remarks = str(row[6]).strip() if len(row) > 6 and row[6] else None

        # Try to parse FSA quantity as float
        try:
            fsa_qty_f = float(fsa_qty) if fsa_qty not in (None, "") else None
        except (TypeError, ValueError):
            fsa_qty_f = None

        try:
            bl_qty_f = float(bl_qty) if bl_qty not in (None, "") else None
        except (TypeError, ValueError):
            bl_qty_f = None

        if fsa_plant and fsa_company and fsa_qty_f is not None:
            records.append({
                "plant_name": fsa_plant,
                "coal_company": fsa_company,
                "quantity_lac_mt": fsa_qty_f,
                "constraint_type": "FSA",
                "fiscal_year": fiscal_year,
                "remarks": None,
            })

        if bl_plant and bl_company and bl_qty_f is not None:
            records.append({
                "plant_name": bl_plant,
                "coal_company": bl_company,
                "quantity_lac_mt": bl_qty_f,
                "constraint_type": "BRIDGE_LINKAGE",
                "fiscal_year": fiscal_year,
                "remarks": bl_remarks,
            })

    return pd.DataFrame(records)
