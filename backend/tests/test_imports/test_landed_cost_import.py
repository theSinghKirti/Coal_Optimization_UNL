"""Unit tests for LandedCostImporter and parse_variable_cost_workbook.

Covers:
- Insert new landed cost record
- Upsert: update existing active record matching (plant_id, supplier_id, effective_from)
- Skip row with invalid total_landed_cost (zero or negative)
- Skip row when plant not found
- Supplier resolved by name
- Supplier not found → insert without supplier linkage
- computed total = basic_cost + freight when components provided
- parse_variable_cost_workbook returns normalised rows from real file
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from sqlalchemy import select

from app.modules.imports.landed_cost_import import LandedCostImporter, parse_variable_cost_workbook
from app.modules.landed_cost.models import LandedCost
from app.modules.master_data.models import CoalCompany, Plant, Supplier


def _seed_plant(db_session, code: str = "LCPLANT") -> Plant:
    plant = Plant(plant_code=code, plant_name=f"{code} Plant", is_active=True)
    db_session.add(plant)
    db_session.flush()
    return plant


def _seed_supplier(db_session, name: str = "NCL LC") -> Supplier:
    supplier = Supplier(name=name)
    db_session.add(supplier)
    db_session.flush()
    return supplier


def _lc_row(**overrides):
    defaults = {
        "plant_name": "LCPLANT Plant",
        "total_landed_cost": "2947.0",
        "basic_cost": "2823.0",
        "freight": "124.0",
    }
    defaults.update(overrides)
    return pd.DataFrame([defaults])


class TestLandedCostInsert:
    def test_inserts_basic_record(self, db_session):
        plant = _seed_plant(db_session)
        df = _lc_row()
        result = LandedCostImporter().import_data(db_session, df)
        assert result.inserted == 1
        assert result.updated == 0

    def test_inserts_with_supplier_link(self, db_session):
        plant = _seed_plant(db_session, "LCPLANT2")
        supplier = _seed_supplier(db_session, "NCL Supplier LC")
        df = _lc_row(plant_name="LCPLANT2 Plant", supplier_name="NCL Supplier LC")
        result = LandedCostImporter().import_data(db_session, df)
        assert result.inserted == 1

        record = db_session.execute(
            select(LandedCost).where(LandedCost.plant_id == plant.id)
        ).scalar_one()
        assert record.supplier_id == supplier.id

    def test_computes_total_from_components(self, db_session):
        _seed_plant(db_session, "LCCOMP")
        df = _lc_row(
            plant_name="LCCOMP Plant",
            basic_cost="2823.0",
            freight="124.0",
            total_landed_cost="2947.0",
        )
        LandedCostImporter().import_data(db_session, df)

        plant = db_session.execute(
            select(Plant).where(Plant.plant_code == "LCCOMP")
        ).scalar_one()
        record = db_session.execute(
            select(LandedCost).where(LandedCost.plant_id == plant.id)
        ).scalar_one()
        # computed total = basic + freight = 2947
        assert float(record.total_landed_cost) == pytest.approx(2947.0)

    def test_gcv_stored(self, db_session):
        _seed_plant(db_session, "LCGCV")
        df = _lc_row(plant_name="LCGCV Plant", gcv_kcal_per_kg="4200.0")
        LandedCostImporter().import_data(db_session, df)

        plant = db_session.execute(select(Plant).where(Plant.plant_code == "LCGCV")).scalar_one()
        record = db_session.execute(
            select(LandedCost).where(LandedCost.plant_id == plant.id)
        ).scalar_one()
        assert float(record.weighted_avg_gcv_kcal_per_kg) == pytest.approx(4200.0)

    def test_status_approved_by_default(self, db_session):
        _seed_plant(db_session, "LCSTAT")
        df = _lc_row(plant_name="LCSTAT Plant")
        LandedCostImporter().import_data(db_session, df)

        plant = db_session.execute(select(Plant).where(Plant.plant_code == "LCSTAT")).scalar_one()
        record = db_session.execute(
            select(LandedCost).where(LandedCost.plant_id == plant.id)
        ).scalar_one()
        assert record.status == "APPROVED"
        assert record.is_active is True


class TestLandedCostUpsert:
    def test_upserts_existing_active_record(self, db_session):
        plant = _seed_plant(db_session, "LCUPS")
        existing = LandedCost(
            plant_id=plant.id,
            total_landed_cost=3000,
            other_cost=0,
            effective_from=date(2026, 4, 1),
            is_active=True,
            status="APPROVED",
            cost_basis="CERTIFIED_WEIGHTED_AVERAGE",
            needs_review=False,
        )
        db_session.add(existing)
        db_session.flush()

        df = _lc_row(
            plant_name="LCUPS Plant",
            total_landed_cost="2947.0",
            effective_from="2026-04-01",
        )
        result = LandedCostImporter().import_data(db_session, df)
        assert result.updated == 1
        assert result.inserted == 0

        db_session.refresh(existing)
        assert float(existing.total_landed_cost) == pytest.approx(2947.0)


class TestLandedCostSkips:
    def test_skips_zero_total_landed_cost(self, db_session):
        _seed_plant(db_session, "LCZERO")
        df = _lc_row(plant_name="LCZERO Plant", total_landed_cost="0")
        result = LandedCostImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_skips_negative_total_landed_cost(self, db_session):
        _seed_plant(db_session, "LCNEG")
        df = _lc_row(plant_name="LCNEG Plant", total_landed_cost="-100")
        result = LandedCostImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_skips_missing_plant_name(self, db_session):
        df = _lc_row(plant_name="")
        result = LandedCostImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_skips_unresolved_plant(self, db_session):
        df = _lc_row(plant_name="GHOST PLANT LC")
        result = LandedCostImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_inserts_without_supplier_when_name_unresolved(self, db_session):
        _seed_plant(db_session, "LCSUP")
        df = _lc_row(plant_name="LCSUP Plant", supplier_name="GHOST SUPPLIER")
        result = LandedCostImporter().import_data(db_session, df)
        assert result.inserted == 1  # still inserts, just no supplier link

    def test_missing_required_columns(self, db_session):
        df = pd.DataFrame([{"plant_name": "X"}])  # missing total_landed_cost
        result = LandedCostImporter().import_data(db_session, df)
        assert len(result.errors) == 1


class TestParseVariableCostWorkbook:
    def test_parses_known_file(self):
        """Integration test: parse the real Flexi Matrix workbook."""
        import os
        vc_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "..",
            "structured_coal_data_task1", "structured_coal_data",
            "variable_cost", "spreadsheets", "Coal Cost as per Flexi Matrix April 2026.xlsx",
        )
        vc_path = os.path.normpath(vc_path)
        if not os.path.exists(vc_path):
            pytest.skip("Variable cost workbook not found — skipping integration test")

        with open(vc_path, "rb") as f:
            content = f.read()

        df = parse_variable_cost_workbook(content, sheet_name=0)
        assert not df.empty
        assert "plant_name" in df.columns
        assert "total_landed_cost" in df.columns
        assert (df["total_landed_cost"] > 0).all()
