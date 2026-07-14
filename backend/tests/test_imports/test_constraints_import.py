"""Unit tests for FSAConstraintImporter.

Covers:
- Insert FSA constraint when plant + company resolved
- Insert BRIDGE_LINKAGE constraint
- Upsert: update quantity when dedup key matches
- Skip row when plant not in DB
- Skip row when coal company not in DB
- Skip summary/total rows
- Skip invalid constraint_type
- Skip negative quantity
- Missing required columns → error
- parse_fsa_workbook produces correct normalised rows
"""

from __future__ import annotations

import io

import pandas as pd
import pytest
from sqlalchemy import select

from app.modules.constraints.models import FSAConstraint
from app.modules.imports.constraints_import import (
    FSAConstraintImporter,
    _is_summary_row,
    parse_fsa_workbook,
)
from app.modules.master_data.models import CoalCompany, Plant


def _seed(db_session, plant_code: str, company_name: str):
    plant = Plant(plant_code=plant_code, plant_name=plant_code + " Plant", is_active=True)
    company = CoalCompany(name=company_name)
    db_session.add_all([plant, company])
    db_session.flush()
    return plant, company


class TestFSAConstraintImporter:
    def test_inserts_fsa_constraint(self, db_session):
        plant, company = _seed(db_session, "ANPARA", "NCL")
        df = pd.DataFrame([{
            "plant_name": "ANPARA Plant",
            "coal_company": "NCL",
            "quantity_lac_mt": 118.64,
            "constraint_type": "FSA",
            "fiscal_year": "2026-27",
        }])
        result = FSAConstraintImporter().import_data(db_session, df)
        assert result.inserted == 1
        assert result.updated == 0
        assert result.skipped == 0

        record = db_session.execute(
            select(FSAConstraint).where(
                FSAConstraint.plant_id == plant.id,
                FSAConstraint.coal_company_id == company.id,
            )
        ).scalar_one()
        assert record.constraint_type == "FSA"
        assert float(record.quantity_lac_mt) == pytest.approx(118.64)
        assert float(record.quantity_mt) == pytest.approx(118.64 * 100_000)
        assert record.status == "APPROVED"
        assert record.is_active is True

    def test_inserts_bridge_linkage_constraint(self, db_session):
        plant, company = _seed(db_session, "HARDUAGANJ", "CCL")
        df = pd.DataFrame([{
            "plant_name": "HARDUAGANJ Plant",
            "coal_company": "CCL",
            "quantity_lac_mt": 12.33,
            "constraint_type": "BRIDGE_LINKAGE",
            "fiscal_year": "2026-27",
            "remarks": "Bridge Linkage Valid till 12.08.2026",
        }])
        result = FSAConstraintImporter().import_data(db_session, df)
        assert result.inserted == 1

        record = db_session.execute(
            select(FSAConstraint).where(FSAConstraint.plant_id == plant.id)
        ).scalar_one()
        assert record.constraint_type == "BRIDGE_LINKAGE"
        # valid_to should be parsed from remarks
        assert record.valid_to is not None

    def test_upserts_existing_constraint(self, db_session):
        plant, company = _seed(db_session, "OBRA", "NCL")
        existing = FSAConstraint(
            constraint_type="FSA",
            plant_id=plant.id,
            coal_company_id=company.id,
            coal_company="NCL",
            fiscal_year="2026-27",
            quantity_lac_mt=30.0,
            quantity_mt=3_000_000,
            annual_contract_quantity_mt=3_000_000,
            status="APPROVED",
            is_active=True,
        )
        db_session.add(existing)
        db_session.flush()

        df = pd.DataFrame([{
            "plant_name": "OBRA Plant",
            "coal_company": "NCL",
            "quantity_lac_mt": 36.18,
            "constraint_type": "FSA",
            "fiscal_year": "2026-27",
        }])
        result = FSAConstraintImporter().import_data(db_session, df)
        assert result.updated == 1
        assert result.inserted == 0

        record = db_session.execute(select(FSAConstraint).where(FSAConstraint.id == existing.id)).scalar_one()
        assert float(record.quantity_lac_mt) == pytest.approx(36.18)

    def test_skips_when_plant_not_found(self, db_session):
        company = CoalCompany(name="NCL Skip")
        db_session.add(company)
        db_session.flush()

        df = pd.DataFrame([{
            "plant_name": "GHOST PLANT",
            "coal_company": "NCL Skip",
            "quantity_lac_mt": 10.0,
            "constraint_type": "FSA",
        }])
        result = FSAConstraintImporter().import_data(db_session, df)
        assert result.skipped == 1
        assert result.inserted == 0

    def test_skips_when_company_not_found(self, db_session):
        plant = Plant(plant_code="PARA", plant_name="PARA Plant", is_active=True)
        db_session.add(plant)
        db_session.flush()

        df = pd.DataFrame([{
            "plant_name": "PARA Plant",
            "coal_company": "GHOST COMPANY",
            "quantity_lac_mt": 10.0,
            "constraint_type": "FSA",
        }])
        result = FSAConstraintImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_skips_invalid_constraint_type(self, db_session):
        plant, company = _seed(db_session, "PTANKI", "CCL")
        df = pd.DataFrame([{
            "plant_name": "PTANKI Plant",
            "coal_company": "CCL",
            "quantity_lac_mt": 5.0,
            "constraint_type": "INVALID_TYPE",
        }])
        result = FSAConstraintImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_skips_negative_quantity(self, db_session):
        plant, company = _seed(db_session, "PTANKI2", "CCL")
        df = pd.DataFrame([{
            "plant_name": "PTANKI2 Plant",
            "coal_company": "CCL",
            "quantity_lac_mt": -5.0,
            "constraint_type": "FSA",
        }])
        result = FSAConstraintImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_missing_columns_returns_error(self, db_session):
        df = pd.DataFrame([{"plant_name": "X", "constraint_type": "FSA"}])
        result = FSAConstraintImporter().import_data(db_session, df)
        assert len(result.errors) == 1


class TestIsSummaryRow:
    @pytest.mark.parametrize("name,expected", [
        ("Anpara Total", True),
        ("Total", True),
        ("Grand Total", True),
        ("Flexi", True),
        ("Anpara", False),
        ("Harduaganj", False),
        (None, True),
    ])
    def test_summary_detection(self, name, expected):
        assert _is_summary_row(name) == expected


class TestParseFsaWorkbook:
    def test_parses_known_file(self):
        """Integration test: parse the actual FSA workbook in the repo."""
        import os
        fsa_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "..",
            "structured_coal_data_task1", "structured_coal_data",
            "fsa", "spreadsheets", "FSA and Bridge Linkage Details 2026-27.xlsx",
        )
        fsa_path = os.path.normpath(fsa_path)
        if not os.path.exists(fsa_path):
            pytest.skip("FSA workbook not found — skipping integration test")

        with open(fsa_path, "rb") as f:
            content = f.read()

        df = parse_fsa_workbook(content)
        assert not df.empty
        assert "plant_name" in df.columns
        assert "coal_company" in df.columns
        assert "quantity_lac_mt" in df.columns
        assert "constraint_type" in df.columns

        # FSA rows should be present
        fsa_rows = df[df["constraint_type"] == "FSA"]
        assert len(fsa_rows) > 0

        # Bridge Linkage rows should be present
        bl_rows = df[df["constraint_type"] == "BRIDGE_LINKAGE"]
        assert len(bl_rows) > 0

        # All quantities should be non-negative (zero is valid for unallocated slots)
        assert (df["quantity_lac_mt"] >= 0).all()
