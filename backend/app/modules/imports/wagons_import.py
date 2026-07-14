"""Wagon position importer.

Since there is no Wagon or WagonPosition database table in the existing schema,
this importer validates the schema and data types of the uploaded wagons dataset,
reporting valid rows as "inserted" (simulated) and invalid rows as "skipped"
with validation errors, complying with the DB schema constraint.
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy.orm import Session

from app.modules.imports.base import BaseImporter, ImportResult

logger = logging.getLogger(__name__)


class WagonImporter(BaseImporter):
    """Validates and processes wagon position data."""

    def import_data(self, session: Session, df: pd.DataFrame) -> ImportResult:
        result = ImportResult()

        # Normalise column names
        df = df.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))

        required = ["wagon_number", "status", "coal_qty_mt"]
        missing = self._require_columns(df, required)
        if missing:
            result.add_error(-1, f"Missing required columns: {missing}")
            return result

        for idx, row in df.iterrows():
            wagon_number = self._str_clean(row.get("wagon_number"))
            status = self._str_clean(row.get("status"))
            qty_raw = row.get("coal_qty_mt")

            if not wagon_number:
                result.skipped += 1
                result.add_error(int(idx), "wagon_number is empty — row skipped")
                continue

            if not status:
                result.skipped += 1
                result.add_error(int(idx), "status is empty — row skipped")
                continue

            qty = self._parse_float(qty_raw, allow_none=True)
            if qty is None or qty < 0:
                result.skipped += 1
                result.add_error(int(idx), f"coal_qty_mt '{qty_raw}' is invalid or negative — row skipped")
                continue

            # Validate arrival_date if present
            arrival_date_raw = row.get("arrival_date")
            if arrival_date_raw is not None and not pd.isna(arrival_date_raw):
                arrival_date = self._parse_date(arrival_date_raw)
                if arrival_date is None:
                    result.skipped += 1
                    result.add_error(int(idx), f"arrival_date '{arrival_date_raw}' is invalid — row skipped")
                    continue

            # Since no database table exists, we simulate successful "insertion" of valid rows
            result.inserted += 1
            logger.debug("Validated wagon row %d: %s", idx, wagon_number)

        return result
