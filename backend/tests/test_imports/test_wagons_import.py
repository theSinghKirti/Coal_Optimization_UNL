"""Unit tests for WagonImporter.

Covers:
- Valid rows return inserted counts
- Missing required columns return error
- Empty/invalid wagon_number skips
- Empty/invalid status skips
- Invalid/negative coal_qty_mt skips
- Valid/invalid arrival_date validation
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.modules.imports.wagons_import import WagonImporter


def _wagon_row(**overrides):
    defaults = {
        "wagon_number": "W12345",
        "status": "LOADED",
        "coal_qty_mt": "55.5",
        "arrival_date": "2026-07-14",
    }
    defaults.update(overrides)
    return pd.DataFrame([defaults])


class TestWagonImporter:
    def test_inserts_valid_row(self):
        df = _wagon_row()
        result = WagonImporter().import_data(None, df)
        assert result.inserted == 1
        assert result.updated == 0
        assert result.skipped == 0
        assert result.errors == []

    def test_skips_empty_wagon_number(self):
        df = _wagon_row(wagon_number="")
        result = WagonImporter().import_data(None, df)
        assert result.skipped == 1
        assert result.inserted == 0

    def test_skips_empty_status(self):
        df = _wagon_row(status="")
        result = WagonImporter().import_data(None, df)
        assert result.skipped == 1
        assert result.inserted == 0

    def test_skips_invalid_coal_qty(self):
        df = _wagon_row(coal_qty_mt="invalid")
        result = WagonImporter().import_data(None, df)
        assert result.skipped == 1

        df_neg = _wagon_row(coal_qty_mt="-10")
        result_neg = WagonImporter().import_data(None, df_neg)
        assert result_neg.skipped == 1

    def test_skips_invalid_arrival_date(self):
        df = _wagon_row(arrival_date="not-a-date")
        result = WagonImporter().import_data(None, df)
        assert result.skipped == 1

    def test_missing_required_columns(self):
        df = pd.DataFrame([{"wagon_number": "W1"}])
        result = WagonImporter().import_data(None, df)
        assert len(result.errors) == 1
