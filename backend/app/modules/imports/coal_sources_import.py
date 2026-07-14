"""Coal sources importer — upserts CoalCompany and Supplier records.

Expected DataFrame columns (case-insensitive):
  For CoalCompany rows (type == "coal_company" or no type column):
    Required: name
    Optional: code

  For Supplier rows (type == "supplier"):
    Required: name
    Optional: code, coal_company_name (resolved to coal_company_id)

Alternatively, a single flat file can contain both:
    name, code, type (coal_company|supplier), coal_company_name
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.imports.base import BaseImporter, ImportResult
from app.modules.master_data.models import CoalCompany, Supplier

logger = logging.getLogger(__name__)


class CoalCompanyImporter(BaseImporter):
    """Upserts CoalCompany records.  Dedup key: ``name`` (unique constraint)."""

    def import_data(self, session: Session, df: pd.DataFrame) -> ImportResult:
        result = ImportResult()
        df = df.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))

        missing = self._require_columns(df, ["name"])
        if missing:
            result.add_error(-1, f"Missing required columns: {missing}")
            return result

        for idx, row in df.iterrows():
            name = self._str_clean(row.get("name"))
            if not name:
                result.skipped += 1
                result.add_error(int(idx), "name is empty — row skipped")
                continue

            code = self._str_clean(row.get("code"))

            existing: CoalCompany | None = session.execute(
                select(CoalCompany).where(CoalCompany.name == name)
            ).scalar_one_or_none()

            if existing:
                if code is not None:
                    existing.code = code
                session.flush()
                result.updated += 1
            else:
                session.add(CoalCompany(name=name, code=code))
                session.flush()
                result.inserted += 1

        return result


class SupplierImporter(BaseImporter):
    """Upserts Supplier records, optionally linking to a CoalCompany by name.

    Dedup key: ``name`` (unique constraint).
    """

    def import_data(self, session: Session, df: pd.DataFrame) -> ImportResult:
        result = ImportResult()
        df = df.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))

        missing = self._require_columns(df, ["name"])
        if missing:
            result.add_error(-1, f"Missing required columns: {missing}")
            return result

        for idx, row in df.iterrows():
            name = self._str_clean(row.get("name"))
            if not name:
                result.skipped += 1
                result.add_error(int(idx), "name is empty — row skipped")
                continue

            code = self._str_clean(row.get("code"))
            coal_company_name = self._str_clean(row.get("coal_company_name"))

            coal_company_id = None
            if coal_company_name:
                company: CoalCompany | None = session.execute(
                    select(CoalCompany).where(CoalCompany.name == coal_company_name)
                ).scalar_one_or_none()
                if company:
                    coal_company_id = company.id
                else:
                    logger.warning(
                        "Row %d: coal_company_name '%s' not found — supplier inserted without linkage",
                        idx,
                        coal_company_name,
                    )

            existing: Supplier | None = session.execute(
                select(Supplier).where(Supplier.name == name)
            ).scalar_one_or_none()

            if existing:
                if code is not None:
                    existing.code = code
                if coal_company_id is not None:
                    existing.coal_company_id = coal_company_id
                session.flush()
                result.updated += 1
            else:
                session.add(Supplier(name=name, code=code, coal_company_id=coal_company_id))
                session.flush()
                result.inserted += 1

        return result


class CoalSourcesImporter(BaseImporter):
    """Combined importer: dispatches rows to CoalCompany or Supplier importers.

    If the DataFrame has a ``type`` column, rows with type == "supplier" go to
    SupplierImporter; everything else goes to CoalCompanyImporter.
    Without a ``type`` column, all rows are treated as CoalCompany rows.
    """

    def import_data(self, session: Session, df: pd.DataFrame) -> ImportResult:
        df = df.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))

        if "type" in df.columns:
            company_df = df[df["type"].str.lower().str.strip() != "supplier"].reset_index(drop=True)
            supplier_df = df[df["type"].str.lower().str.strip() == "supplier"].reset_index(drop=True)
        else:
            company_df = df.copy()
            supplier_df = pd.DataFrame()

        combined = ImportResult()
        if not company_df.empty:
            r = CoalCompanyImporter().import_data(session, company_df)
            combined.inserted += r.inserted
            combined.updated += r.updated
            combined.skipped += r.skipped
            combined.errors.extend(r.errors)

        if not supplier_df.empty:
            r = SupplierImporter().import_data(session, supplier_df)
            combined.inserted += r.inserted
            combined.updated += r.updated
            combined.skipped += r.skipped
            combined.errors.extend(r.errors)

        return combined
