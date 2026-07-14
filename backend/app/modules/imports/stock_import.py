"""Daily stock importer — upserts DailyStock records.

The daily stock PDFs / images in the repo are not machine-parseable without
OCR, so this importer accepts a **structured CSV or Excel** upload.

Expected columns (case-insensitive):
  Required:
    plant_code      — must match an existing Plant.plant_code
    report_date     — ISO date (YYYY-MM-DD) or DD/MM/YYYY
    opening_stock_mt
    receipt_mt
    consumption_mt
    closing_stock_mt
  Optional:
    remarks         — required by the service layer when reconciliation diff > tolerance

Dedup key: (plant_id, report_date) — maps to the DB unique constraint
  uq_daily_stock_plant_date.  If a record exists → update all numeric fields.

Reconciliation fields are recomputed on every import row:
  expected_closing_stock_mt = opening + receipt - consumption
  reconciliation_difference_mt = closing - expected_closing
  validation_status = "warning" if |diff| > 0.01 else "ok"
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.daily_stock.models import DailyStock
from app.modules.imports.base import BaseImporter, ImportResult
from app.modules.master_data.models import Plant

logger = logging.getLogger(__name__)

settings = get_settings()
_TOLERANCE = settings.stock_reconciliation_tolerance_mt


def _resolve_plant(session: Session, plant_code: str) -> Plant | None:
    return session.execute(
        select(Plant).where(Plant.plant_code == plant_code)
    ).scalar_one_or_none()


class DailyStockImporter(BaseImporter):
    """Upsert DailyStock rows. Dedup key: (plant_id, report_date)."""

    def import_data(self, session: Session, df: pd.DataFrame) -> ImportResult:
        result = ImportResult()
        df = df.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))

        required = [
            "plant_code", "report_date",
            "opening_stock_mt", "receipt_mt", "consumption_mt", "closing_stock_mt",
        ]
        missing = self._require_columns(df, required)
        if missing:
            result.add_error(-1, f"Missing required columns: {missing}")
            return result

        for idx, row in df.iterrows():
            plant_code = self._str_clean(row.get("plant_code"))
            report_date = self._parse_date(row.get("report_date"))

            if not plant_code:
                result.skipped += 1
                result.add_error(int(idx), "plant_code is empty — row skipped")
                continue

            if report_date is None:
                result.skipped += 1
                result.add_error(int(idx), f"report_date invalid for plant '{plant_code}' — row skipped")
                continue

            opening = self._parse_float(row.get("opening_stock_mt"), allow_none=False)
            receipt = self._parse_float(row.get("receipt_mt"), allow_none=False)
            consumption = self._parse_float(row.get("consumption_mt"), allow_none=False)
            closing = self._parse_float(row.get("closing_stock_mt"), allow_none=False)

            parse_errors = []
            if opening is None:
                parse_errors.append("opening_stock_mt")
            if receipt is None:
                parse_errors.append("receipt_mt")
            if consumption is None:
                parse_errors.append("consumption_mt")
            if closing is None:
                parse_errors.append("closing_stock_mt")

            if parse_errors:
                result.skipped += 1
                result.add_error(int(idx), f"Non-numeric values in: {parse_errors} — row skipped")
                continue

            if any(v < 0 for v in (opening, receipt, consumption, closing)):  # type: ignore[operator]
                result.skipped += 1
                result.add_error(int(idx), f"Negative stock values for plant '{plant_code}' on {report_date} — row skipped")
                continue

            remarks = self._str_clean(row.get("remarks"))

            # Compute reconciliation
            expected_closing = opening + receipt - consumption  # type: ignore[operator]
            diff = closing - expected_closing  # type: ignore[operator]
            is_warning = abs(diff) > _TOLERANCE
            validation_status = "warning" if is_warning else "ok"

            if is_warning and not remarks:
                result.skipped += 1
                result.add_error(
                    int(idx),
                    f"Reconciliation diff {diff:.3f} > tolerance for '{plant_code}' on {report_date}; "
                    f"remarks required for warning records — row skipped",
                )
                continue

            plant = _resolve_plant(session, plant_code)
            if not plant:
                result.skipped += 1
                result.add_error(int(idx), f"Plant code '{plant_code}' not found in DB — skipped")
                continue

            existing: DailyStock | None = session.execute(
                select(DailyStock).where(
                    DailyStock.plant_id == plant.id,
                    DailyStock.report_date == report_date,
                )
            ).scalar_one_or_none()

            if existing:
                existing.opening_stock_mt = opening  # type: ignore[assignment]
                existing.receipt_mt = receipt  # type: ignore[assignment]
                existing.consumption_mt = consumption  # type: ignore[assignment]
                existing.closing_stock_mt = closing  # type: ignore[assignment]
                existing.expected_closing_stock_mt = expected_closing  # type: ignore[assignment]
                existing.reconciliation_difference_mt = diff  # type: ignore[assignment]
                existing.validation_status = validation_status
                existing.remarks = remarks
                session.flush()
                result.updated += 1
            else:
                record = DailyStock(
                    plant_id=plant.id,
                    report_date=report_date,
                    opening_stock_mt=opening,  # type: ignore[arg-type]
                    receipt_mt=receipt,  # type: ignore[arg-type]
                    consumption_mt=consumption,  # type: ignore[arg-type]
                    closing_stock_mt=closing,  # type: ignore[arg-type]
                    expected_closing_stock_mt=expected_closing,  # type: ignore[arg-type]
                    reconciliation_difference_mt=diff,  # type: ignore[arg-type]
                    validation_status=validation_status,
                    remarks=remarks,
                )
                session.add(record)
                session.flush()
                result.inserted += 1

        return result
