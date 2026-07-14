"""Unit tests for CoalCompanyImporter, SupplierImporter, and CoalSourcesImporter.

Covers:
- Insert new coal companies
- Upsert existing company (update code)
- Insert supplier linked to company by name
- Supplier falls back gracefully when company not found
- CoalSourcesImporter routes rows by 'type' column
- Missing 'name' column → error
- Empty 'name' → skip
"""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import select

from app.modules.imports.coal_sources_import import (
    CoalCompanyImporter,
    CoalSourcesImporter,
    SupplierImporter,
)
from app.modules.master_data.models import CoalCompany, Supplier


class TestCoalCompanyImporter:
    def test_inserts_new_company(self, db_session):
        df = pd.DataFrame([{"name": "NCL Test", "code": "NCL"}])
        result = CoalCompanyImporter().import_data(db_session, df)
        assert result.inserted == 1
        assert result.updated == 0

        company = db_session.execute(
            select(CoalCompany).where(CoalCompany.name == "NCL Test")
        ).scalar_one()
        assert company.code == "NCL"

    def test_upserts_existing_company_code(self, db_session):
        db_session.add(CoalCompany(name="BCCL Test", code="OLD"))
        db_session.flush()

        df = pd.DataFrame([{"name": "BCCL Test", "code": "BCCL"}])
        result = CoalCompanyImporter().import_data(db_session, df)
        assert result.updated == 1
        assert result.inserted == 0

        company = db_session.execute(
            select(CoalCompany).where(CoalCompany.name == "BCCL Test")
        ).scalar_one()
        assert company.code == "BCCL"

    def test_inserts_multiple_companies(self, db_session):
        df = pd.DataFrame([
            {"name": "CCL Test"},
            {"name": "SECL Test"},
        ])
        result = CoalCompanyImporter().import_data(db_session, df)
        assert result.inserted == 2

    def test_skips_empty_name(self, db_session):
        df = pd.DataFrame([{"name": "", "code": "X"}])
        result = CoalCompanyImporter().import_data(db_session, df)
        assert result.skipped == 1
        assert result.inserted == 0

    def test_missing_name_column_returns_error(self, db_session):
        df = pd.DataFrame([{"code": "X"}])
        result = CoalCompanyImporter().import_data(db_session, df)
        assert len(result.errors) == 1
        assert "name" in result.errors[0]["error"]


class TestSupplierImporter:
    def test_inserts_supplier_without_company(self, db_session):
        df = pd.DataFrame([{"name": "Supplier Alpha", "code": "SA"}])
        result = SupplierImporter().import_data(db_session, df)
        assert result.inserted == 1

        supplier = db_session.execute(
            select(Supplier).where(Supplier.name == "Supplier Alpha")
        ).scalar_one()
        assert supplier.coal_company_id is None

    def test_links_supplier_to_existing_company(self, db_session):
        company = CoalCompany(name="ECL Test Link", code="ECL")
        db_session.add(company)
        db_session.flush()

        df = pd.DataFrame([{
            "name": "ECL Supplier",
            "coal_company_name": "ECL Test Link",
        }])
        result = SupplierImporter().import_data(db_session, df)
        assert result.inserted == 1

        supplier = db_session.execute(
            select(Supplier).where(Supplier.name == "ECL Supplier")
        ).scalar_one()
        assert supplier.coal_company_id == company.id

    def test_supplier_inserts_even_when_company_not_found(self, db_session):
        df = pd.DataFrame([{
            "name": "Orphan Supplier",
            "coal_company_name": "NonExistent Co",
        }])
        result = SupplierImporter().import_data(db_session, df)
        assert result.inserted == 1

        supplier = db_session.execute(
            select(Supplier).where(Supplier.name == "Orphan Supplier")
        ).scalar_one()
        assert supplier.coal_company_id is None

    def test_upserts_existing_supplier(self, db_session):
        db_session.add(Supplier(name="Existing Supplier", code="OLD"))
        db_session.flush()

        df = pd.DataFrame([{"name": "Existing Supplier", "code": "NEW"}])
        result = SupplierImporter().import_data(db_session, df)
        assert result.updated == 1

        supplier = db_session.execute(
            select(Supplier).where(Supplier.name == "Existing Supplier")
        ).scalar_one()
        assert supplier.code == "NEW"


class TestCoalSourcesImporter:
    def test_routes_by_type_column(self, db_session):
        df = pd.DataFrame([
            {"name": "NCL Combined", "code": "NCL", "type": "coal_company"},
            {"name": "NCL Sub Supplier", "type": "supplier", "coal_company_name": "NCL Combined"},
        ])
        result = CoalSourcesImporter().import_data(db_session, df)
        assert result.inserted == 2

    def test_all_rows_treated_as_company_without_type_column(self, db_session):
        df = pd.DataFrame([
            {"name": "SCCL No Type"},
            {"name": "WCL No Type"},
        ])
        result = CoalSourcesImporter().import_data(db_session, df)
        assert result.inserted == 2
        # Verify both went to CoalCompany
        companies = db_session.execute(
            select(CoalCompany).where(CoalCompany.name.in_(["SCCL No Type", "WCL No Type"]))
        ).scalars().all()
        assert len(companies) == 2
