"""Unit tests for PlantImporter.

Covers:
- Happy path: insert new plants
- Upsert: update existing plant name/is_active
- Skip empty plant_code
- Skip empty plant_name
- Skip plant_code > 32 chars
- Optional alias column creates PlantAlias
- Duplicate alias on same plant is idempotent (no duplicate)
- Correct inserted / updated / skipped counts
"""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import select

from app.modules.imports.plants_import import PlantImporter
from app.modules.master_data.models import Plant, PlantAlias


def _make_df(**kwargs) -> pd.DataFrame:
    """Build a one-row DataFrame from keyword args."""
    return pd.DataFrame([kwargs])


class TestPlantImporterInsert:
    def test_inserts_new_plant(self, db_session):
        df = _make_df(plant_code="TEST01", plant_name="Test Plant One")
        result = PlantImporter().import_data(db_session, df)
        assert result.inserted == 1
        assert result.updated == 0
        assert result.skipped == 0
        assert result.errors == []

        plant = db_session.execute(select(Plant).where(Plant.plant_code == "TEST01")).scalar_one()
        assert plant.plant_name == "Test Plant One"
        assert plant.is_active is True

    def test_inserts_multiple_plants(self, db_session):
        df = pd.DataFrame([
            {"plant_code": "A001", "plant_name": "Alpha Plant"},
            {"plant_code": "B002", "plant_name": "Beta Plant"},
        ])
        result = PlantImporter().import_data(db_session, df)
        assert result.inserted == 2
        assert result.updated == 0

    def test_is_active_defaults_to_true(self, db_session):
        df = _make_df(plant_code="ACTIVE1", plant_name="Active Plant")
        PlantImporter().import_data(db_session, df)
        plant = db_session.execute(select(Plant).where(Plant.plant_code == "ACTIVE1")).scalar_one()
        assert plant.is_active is True

    def test_is_active_false(self, db_session):
        df = _make_df(plant_code="INACT1", plant_name="Inactive Plant", is_active="false")
        PlantImporter().import_data(db_session, df)
        plant = db_session.execute(select(Plant).where(Plant.plant_code == "INACT1")).scalar_one()
        assert plant.is_active is False


class TestPlantImporterUpsert:
    def test_updates_existing_plant_name(self, db_session):
        # Seed
        existing = Plant(plant_code="UPS01", plant_name="Old Name", is_active=True)
        db_session.add(existing)
        db_session.flush()

        df = _make_df(plant_code="UPS01", plant_name="New Name")
        result = PlantImporter().import_data(db_session, df)
        assert result.inserted == 0
        assert result.updated == 1

        plant = db_session.execute(select(Plant).where(Plant.plant_code == "UPS01")).scalar_one()
        assert plant.plant_name == "New Name"

    def test_updates_is_active(self, db_session):
        existing = Plant(plant_code="UPS02", plant_name="Some Plant", is_active=True)
        db_session.add(existing)
        db_session.flush()

        df = _make_df(plant_code="UPS02", plant_name="Some Plant", is_active="no")
        PlantImporter().import_data(db_session, df)

        plant = db_session.execute(select(Plant).where(Plant.plant_code == "UPS02")).scalar_one()
        assert plant.is_active is False


class TestPlantImporterSkips:
    def test_skips_empty_plant_code(self, db_session):
        df = _make_df(plant_code="", plant_name="No Code Plant")
        result = PlantImporter().import_data(db_session, df)
        assert result.skipped == 1
        assert result.inserted == 0
        assert len(result.errors) == 1

    def test_skips_nan_plant_code(self, db_session):
        import math
        df = _make_df(plant_code=float("nan"), plant_name="NaN Code Plant")
        result = PlantImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_skips_empty_plant_name(self, db_session):
        df = _make_df(plant_code="NNAME1", plant_name="")
        result = PlantImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_skips_plant_code_over_32_chars(self, db_session):
        long_code = "X" * 33
        df = _make_df(plant_code=long_code, plant_name="Long Code Plant")
        result = PlantImporter().import_data(db_session, df)
        assert result.skipped == 1

    def test_missing_required_column_returns_error(self, db_session):
        df = pd.DataFrame([{"plant_name": "Only Name"}])
        result = PlantImporter().import_data(db_session, df)
        assert len(result.errors) == 1
        assert "plant_code" in result.errors[0]["error"]


class TestPlantImporterAlias:
    def test_creates_alias_for_new_plant(self, db_session):
        df = _make_df(plant_code="ALI01", plant_name="Alias Plant", alias_name="AP1")
        result = PlantImporter().import_data(db_session, df)
        assert result.inserted == 1

        plant = db_session.execute(select(Plant).where(Plant.plant_code == "ALI01")).scalar_one()
        alias = db_session.execute(
            select(PlantAlias).where(PlantAlias.alias_name == "AP1")
        ).scalar_one()
        assert alias.plant_id == plant.id

    def test_idempotent_alias_does_not_duplicate(self, db_session):
        # Create plant + alias
        plant = Plant(plant_code="ALI02", plant_name="Alias Plant 2", is_active=True)
        db_session.add(plant)
        db_session.flush()
        db_session.add(PlantAlias(plant_id=plant.id, alias_name="AP2"))
        db_session.flush()

        # Re-import same alias
        df = _make_df(plant_code="ALI02", plant_name="Alias Plant 2", alias_name="AP2")
        result = PlantImporter().import_data(db_session, df)
        assert result.updated == 1  # plant updated (same values)

        aliases = db_session.execute(
            select(PlantAlias).where(PlantAlias.alias_name == "AP2")
        ).scalars().all()
        assert len(aliases) == 1  # still only one
