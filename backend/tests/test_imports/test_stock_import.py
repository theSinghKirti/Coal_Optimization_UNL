"""Unit tests for DailyStockImporter.

Covers:
- Insert valid stock row
- Upsert: update existing (plant_id, report_date)
- Reconciliation computation (expected_closing, diff, validation_status)
- Skip row when plant not in DB
- Skip non-numeric stock values
- Skip negative values
- Skip warning row with no remarks
- Warning row with remarks is inserted with validation_status="warning"
- Invalid date skips row
- Missing required columns returns error
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from sqlalchemy import select

from app.modules.daily_stock.models import DailyStock
from app.modules.imports.stock_import import DailyStockImporter
from app.modules.master_data.models import Plant


def _seed_plant(db_session, code: str = "TESTPLANT") -> Plant:
    plant = Plant(plant_code=code, plant_name=f"{code} Plant", is_active=True)
    db_session.add(plant)
    db_session.flush()
    return plant


def _stock_row(**overrides):
    defaults = {
        "plant_code": "TESTPLANT",
        "report_date": "2026-03-01",
        "opening_stock_mt": "1000.0",
        "receipt_mt": "500.0",
        "consumption_mt": "300.0",
        "closing_stock_mt": "1200.0",
    }
    defaults.update(overrides)
    return pd.DataFrame([defaults])


class TestDailyStockInsert:
    def test_inserts_valid_row(self, db_session):
        plant = _seed_plant(db_session)
        df = _stock_row()
        result = DailyStockImporter().import_data(db_session, df)
        assert result.inserted == 1
        assert result.updated == 0
        assert result.skipped == 0

    def test_reconciliation_computed_correctly(self, db_session):
        plant = _seed_plant(db_session)
        df = _stock_row(
            opening_stock_mt="1000.0",
            receipt_mt="500.0",
            consumption_mt="300.0",
            closing_stock_mt="1200.0",
        )
        DailyStockImporter().import_data(db_session, df)

        record = db_session.execute(select(DailyStock).where(DailyStock.plant_id == plant.id)).scalar_one()
        assert float(record.expected_closing_stock_mt) == pytest.approx(1200.0)
        assert float(record.reconciliation_difference_mt) == pytest.approx(0.0)
        assert record.validation_status == "ok"

    def test_warning_status_with_remarks(self, db_session):
        plant = _seed_plant(db_session, "WARNPLANT")
        df = _stock_row(
            plant_code="WARNPLANT",
            opening_stock_mt="1000.0",
            receipt_mt="500.0",
            consumption_mt="300.0",
            closing_stock_mt="1250.0",   # diff = 50 > tolerance
            remarks="Measurement discrepancy noted",
        )
        result = DailyStockImporter().import_data(db_session, df)
        assert result.inserted == 1

        record = db_session.execute(
            select(DailyStock).where(DailyStock.plant_id == plant.id)
        ).scalar_one()
        assert record.validation_status == "warning"
        assert float(record.reconciliation_difference_mt) == pytest.approx(50.0)


class TestDailyStockUpsert:
    def test_upserts_existing_record(self, db_session):
        plant = _seed_plant(db_session, "UPSPLANT")
        # Seed existing record
        existing = DailyStock(
            plant_id=plant.id,
            report_date=date(2026, 3, 1),
            opening_stock_mt=900,
            receipt_mt=400,
            consumption_mt=200,
            closing_stock_mt=1100,
            expected_closing_stock_mt=1100,
            reconciliation_difference_mt=0,
            validation_status="ok",
        )
        db_session.add(existing)
        db_session.flush()

        df = _stock_row(
            plant_code="UPSPLANT",
            opening_stock_mt="1000.0",
            receipt_mt="500.0",
            consumption_mt="300.0",
            closing_stock_mt="1200.0",
        )
        result = DailyStockImporter().import_data(db_session, df)
        assert result.updated == 1
        assert result.inserted == 0

        record = db_session.execute(select(DailyStock).where(DailyStock.id == existing.id)).scalar_one()
        assert float(record.opening_stock_mt) == pytest.approx(1000.0)


class TestDailyStockSkips:
    def test_skips_unknown_plant(self, db_session):
        df = _stock_row(plant_code="GHOST999")
        result = DailyStockImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_skips_invalid_date(self, db_session):
        _seed_plant(db_session)
        df = _stock_row(report_date="not-a-date")
        result = DailyStockImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_skips_non_numeric_stock(self, db_session):
        _seed_plant(db_session)
        df = _stock_row(opening_stock_mt="N/A")
        result = DailyStockImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_skips_negative_value(self, db_session):
        _seed_plant(db_session)
        df = _stock_row(opening_stock_mt="-100")
        result = DailyStockImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_skips_warning_row_without_remarks(self, db_session):
        _seed_plant(db_session, "NOWARNREM")
        df = _stock_row(
            plant_code="NOWARNREM",
            closing_stock_mt="1999.0",  # big diff from expected 1200
        )
        result = DailyStockImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_skips_empty_plant_code(self, db_session):
        df = _stock_row(plant_code="")
        result = DailyStockImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_missing_columns_returns_error(self, db_session):
        df = pd.DataFrame([{"plant_code": "X", "report_date": "2026-01-01"}])
        result = DailyStockImporter().import_data(db_session, df)
        assert len(result.errors) == 1

    def test_accepts_dd_mm_yyyy_date_format(self, db_session):
        _seed_plant(db_session, "DDFMT")
        df = _stock_row(plant_code="DDFMT", report_date="15/03/2026")
        result = DailyStockImporter().import_data(db_session, df)
        assert result.inserted == 1
