"""Shared base classes and utilities for all ETL importers.

Every importer must:
  1. Extend ``BaseImporter``
  2. Implement ``import_data(session, df) -> ImportResult``
  3. Call ``_commit_or_rollback`` exactly once per import run (handled here)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class ImportResult:
    """Aggregated outcome of a single import run."""

    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "success" if not self.errors else "partial"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
        }

    def add_error(self, row_index: int, message: str, row_data: dict | None = None) -> None:
        entry: dict[str, Any] = {"row": row_index, "error": message}
        if row_data:
            entry["data"] = row_data
        self.errors.append(entry)
        logger.warning("Row %d skipped — %s", row_index, message)


# ---------------------------------------------------------------------------
# Abstract base importer
# ---------------------------------------------------------------------------

class BaseImporter(ABC):
    """Abstract base for all dataset importers."""

    @abstractmethod
    def import_data(self, session: Session, df: pd.DataFrame) -> ImportResult:
        """Import records from *df* into the database via *session*.

        The implementation must **not** call ``session.commit()`` or
        ``session.rollback()`` — that is the caller's responsibility
        (handled by ``run_import``).
        """

    # ------------------------------------------------------------------
    # Shared validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _require_columns(df: pd.DataFrame, required: list[str]) -> list[str]:
        """Return list of missing column names (empty list when all present)."""
        return [c for c in required if c not in df.columns]

    @staticmethod
    def _parse_float(value: Any, *, allow_none: bool = True) -> float | None:
        """Coerce *value* to float.  Returns ``None`` on failure when allowed."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None if allow_none else None
        try:
            result = float(str(value).replace(",", "").strip())
            return result
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        """Coerce *value* to ``datetime.date``.

        Accepts:
        - ``datetime.date`` / ``datetime.datetime`` objects (from openpyxl)
        - ISO strings ``YYYY-MM-DD``
        - Indian format ``DD/MM/YYYY`` or ``DD-MM-YYYY``
        - Excel numeric date floats
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        s = str(value).strip()
        if not s or s.lower() in ("nan", "none", "nat", ""):
            return None
        # Try common formats
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        # Attempt pandas parsing as fallback
        try:
            return pd.to_datetime(s, dayfirst=True).date()
        except Exception:
            return None

    @staticmethod
    def _str_clean(value: Any) -> str | None:
        """Strip and return string; return ``None`` for empty/NaN."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        s = str(value).strip()
        return s if s else None


# ---------------------------------------------------------------------------
# Top-level helper used by the router
# ---------------------------------------------------------------------------

def run_import(
    session: Session,
    importer: BaseImporter,
    df: pd.DataFrame,
    *,
    dataset_label: str = "dataset",
) -> ImportResult:
    """Execute *importer* inside a try/except that rolls back on any error.

    This is the **only** function that calls ``session.commit()``
    or ``session.rollback()``.
    """
    import time

    logger.info("Import started — %s (%d rows)", dataset_label, len(df))
    t0 = time.perf_counter()
    result = ImportResult()
    try:
        result = importer.import_data(session, df)
        session.commit()
        elapsed = time.perf_counter() - t0
        logger.info(
            "Import finished — %s | inserted=%d updated=%d skipped=%d errors=%d (%.2fs)",
            dataset_label,
            result.inserted,
            result.updated,
            result.skipped,
            len(result.errors),
            elapsed,
        )
    except Exception as exc:
        session.rollback()
        logger.error("Import FAILED — %s: %s", dataset_label, exc, exc_info=True)
        result.errors.append({"row": -1, "error": f"Fatal import error: {exc}"})
        result.status  # noqa – property access just for mypy
    return result


def read_upload(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Parse uploaded file bytes into a DataFrame.

    Supports .xlsx, .xls, and .csv files.
    Raises ``ValueError`` for unsupported extensions.
    """
    import io

    lower = filename.lower()
    if lower.endswith(".csv"):
        return pd.read_csv(io.BytesIO(file_bytes), dtype=str)
    if lower.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(file_bytes), dtype=str)
    raise ValueError(f"Unsupported file type: '{filename}'. Only .csv, .xlsx and .xls are accepted.")
