"""Plant importer — upserts Plant and PlantAlias records.

Expected DataFrame columns (case-insensitive, normalised on load):
  Required:
    plant_code   — unique business key, max 32 chars
    plant_name   — human-readable name, max 255 chars
  Optional:
    is_active    — bool-ish (True/False/1/0/yes/no), defaults to True
    alias_name   — if present, a PlantAlias is created/skipped for this plant
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.imports.base import BaseImporter, ImportResult
from app.modules.master_data.models import Plant, PlantAlias

logger = logging.getLogger(__name__)

_BOOL_TRUE = {"true", "1", "yes", "y"}
_BOOL_FALSE = {"false", "0", "no", "n"}


def _parse_bool(value, *, default: bool = True) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    s = str(value).strip().lower()
    if s in _BOOL_TRUE:
        return True
    if s in _BOOL_FALSE:
        return False
    return default


class PlantImporter(BaseImporter):
    """Upsert plants from a structured DataFrame.

    Dedup key: ``plant_code`` (unique constraint in DB).
    - If a plant with that code exists → update ``plant_name`` and ``is_active``.
    - Otherwise → insert a new Plant row.
    - If column ``alias_name`` is present → upsert a PlantAlias row for that plant.
    """

    def import_data(self, session: Session, df: pd.DataFrame) -> ImportResult:
        result = ImportResult()

        # Normalise column names
        df = df.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))

        missing = self._require_columns(df, ["plant_code", "plant_name"])
        if missing:
            result.add_error(-1, f"Missing required columns: {missing}")
            return result

        for idx, row in df.iterrows():
            plant_code = self._str_clean(row.get("plant_code"))
            plant_name = self._str_clean(row.get("plant_name"))

            if not plant_code:
                result.skipped += 1
                result.add_error(int(idx), "plant_code is empty — row skipped")
                continue

            if not plant_name:
                result.skipped += 1
                result.add_error(int(idx), f"plant_name is empty for code '{plant_code}' — row skipped")
                continue

            if len(plant_code) > 32:
                result.skipped += 1
                result.add_error(int(idx), f"plant_code '{plant_code}' exceeds 32 chars — row skipped")
                continue

            is_active = _parse_bool(row.get("is_active"), default=True)

            # Upsert
            existing: Plant | None = session.execute(
                select(Plant).where(Plant.plant_code == plant_code)
            ).scalar_one_or_none()

            if existing:
                existing.plant_name = plant_name
                existing.is_active = is_active
                session.flush()
                result.updated += 1
                logger.debug("Updated plant '%s'", plant_code)
                plant = existing
            else:
                plant = Plant(plant_code=plant_code, plant_name=plant_name, is_active=is_active)
                session.add(plant)
                session.flush()
                result.inserted += 1
                logger.debug("Inserted plant '%s'", plant_code)

            # Optional alias
            alias_name = self._str_clean(row.get("alias_name"))
            if alias_name:
                existing_alias: PlantAlias | None = session.execute(
                    select(PlantAlias).where(PlantAlias.alias_name == alias_name)
                ).scalar_one_or_none()
                if not existing_alias:
                    session.add(PlantAlias(plant_id=plant.id, alias_name=alias_name))
                    session.flush()
                    logger.debug("Inserted alias '%s' for plant '%s'", alias_name, plant_code)

        return result
