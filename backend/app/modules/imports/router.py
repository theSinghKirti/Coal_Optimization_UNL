"""Import API router — multipart file upload endpoints for each dataset.

All endpoints:
  - Accept a multipart file upload (.csv, .xlsx, .xls)
  - Validate the file and parse it into a DataFrame
  - Run the appropriate importer inside a single DB transaction
  - Return an ImportResult JSON response

Response shape:
  {
    "status":   "success" | "partial",
    "inserted": int,
    "updated":  int,
    "skipped":  int,
    "errors":   [{"row": int, "error": str}, ...]
  }

Endpoints:
  POST /api/v1/import/plants
  POST /api/v1/import/coal-sources
  POST /api/v1/import/constraints          (normalised CSV/Excel)
  POST /api/v1/import/constraints/fsa-workbook  (native FSA xlsx)
  POST /api/v1/import/stock
  POST /api/v1/import/landed-costs         (normalised CSV/Excel)
  POST /api/v1/import/landed-costs/workbook (native Flexi Matrix xlsx)
  POST /api/v1/import/allocations
  POST /api/v1/import/all                  (runs plants + coal-sources + constraints + landed-costs)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.imports.allocation_import import AllocationImporter
from app.modules.imports.base import ImportResult, read_upload, run_import
from app.modules.imports.coal_sources_import import CoalSourcesImporter
from app.modules.imports.constraints_import import (
    FSAConstraintImporter,
    parse_fsa_workbook,
)
from app.modules.imports.landed_cost_import import (
    LandedCostImporter,
    parse_variable_cost_workbook,
)
from app.modules.imports.plants_import import PlantImporter
from app.modules.imports.stock_import import DailyStockImporter
from app.modules.imports.wagons_import import WagonImporter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/import", tags=["Data Import"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_file(file: UploadFile) -> tuple[bytes, str]:
    """Read upload and return (bytes, filename)."""
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    return content, file.filename or "upload"


def _result_response(result: ImportResult) -> dict[str, Any]:
    return result.to_dict()


# ---------------------------------------------------------------------------
# Plants
# ---------------------------------------------------------------------------

@router.post(
    "/plants",
    summary="Import Plants",
    description=(
        "Upload a CSV or Excel file with columns: plant_code, plant_name, is_active (optional), "
        "alias_name (optional).  Upserts plants by plant_code."
    ),
)
def import_plants(
    file: UploadFile = File(..., description="CSV or Excel file (.csv/.xlsx/.xls)"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content, filename = _read_file(file)
    try:
        df = read_upload(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    result = run_import(db, PlantImporter(), df, dataset_label="plants")
    return _result_response(result)


# ---------------------------------------------------------------------------
# Coal Sources
# ---------------------------------------------------------------------------

@router.post(
    "/coal-sources",
    summary="Import Coal Companies and Suppliers",
    description=(
        "Upload a CSV or Excel file with columns: name, code (optional), "
        "type (coal_company|supplier), coal_company_name (optional).  "
        "Upserts CoalCompany and Supplier records."
    ),
)
def import_coal_sources(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content, filename = _read_file(file)
    try:
        df = read_upload(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    result = run_import(db, CoalSourcesImporter(), df, dataset_label="coal_sources")
    return _result_response(result)


# ---------------------------------------------------------------------------
# FSA / Bridge Linkage Constraints
# ---------------------------------------------------------------------------

@router.post(
    "/constraints",
    summary="Import FSA/Bridge Linkage Constraints (normalised CSV/Excel)",
    description=(
        "Upload a normalised CSV or Excel with columns: plant_name, coal_company, "
        "quantity_lac_mt, constraint_type (FSA|BRIDGE_LINKAGE), fiscal_year (optional), remarks (optional). "
        "Upserts FSAConstraint records."
    ),
)
def import_constraints(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content, filename = _read_file(file)
    try:
        df = read_upload(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    result = run_import(db, FSAConstraintImporter(), df, dataset_label="constraints")
    return _result_response(result)


@router.post(
    "/constraints/fsa-workbook",
    summary="Import from native FSA/Bridge Linkage Excel workbook",
    description=(
        "Upload the 'FSA and Bridge Linkage Details' Excel workbook directly.  "
        "The endpoint parses its two-section layout automatically before importing."
    ),
)
def import_constraints_fsa_workbook(
    file: UploadFile = File(..., description="Native FSA xlsx workbook"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content, filename = _read_file(file)
    if not filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="FSA workbook must be an .xlsx or .xls file.",
        )
    try:
        df = parse_fsa_workbook(content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse FSA workbook: {exc}",
        )

    result = run_import(db, FSAConstraintImporter(), df, dataset_label="constraints/fsa-workbook")
    return _result_response(result)


# ---------------------------------------------------------------------------
# Daily Stock
# ---------------------------------------------------------------------------

@router.post(
    "/stock",
    summary="Import Daily Coal Stock",
    description=(
        "Upload a CSV or Excel with columns: plant_code, report_date, opening_stock_mt, "
        "receipt_mt, consumption_mt, closing_stock_mt, remarks (optional).  "
        "Upserts DailyStock records by (plant_code, report_date)."
    ),
)
def import_stock(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content, filename = _read_file(file)
    try:
        df = read_upload(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    result = run_import(db, DailyStockImporter(), df, dataset_label="daily_stock")
    return _result_response(result)


# ---------------------------------------------------------------------------
# Landed Costs
# ---------------------------------------------------------------------------

@router.post(
    "/landed-costs",
    summary="Import Landed Costs (normalised CSV/Excel)",
    description=(
        "Upload a normalised CSV or Excel with columns: plant_name, total_landed_cost, "
        "supplier_name (optional), basic_cost, freight, gcv_kcal_per_kg, effective_from, effective_to.  "
        "Upserts LandedCost records."
    ),
)
def import_landed_costs(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content, filename = _read_file(file)
    try:
        df = read_upload(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    result = run_import(db, LandedCostImporter(), df, dataset_label="landed_costs")
    return _result_response(result)


@router.post(
    "/landed-costs/workbook",
    summary="Import from native Flexi Matrix / Variable Cost Excel workbook",
    description=(
        "Upload the 'Coal Cost as per Flexi Matrix' Excel workbook directly.  "
        "Optionally pass ?sheet=<name> to select a specific sheet (default: first sheet)."
    ),
)
def import_landed_costs_workbook(
    file: UploadFile = File(...),
    sheet: str | int = 0,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content, filename = _read_file(file)
    if not filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Workbook must be an .xlsx or .xls file.",
        )
    try:
        sheet_arg: str | int = int(sheet) if str(sheet).isdigit() else sheet
        df = parse_variable_cost_workbook(content, sheet_name=sheet_arg)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse workbook: {exc}",
        )

    result = run_import(db, LandedCostImporter(), df, dataset_label="landed_costs/workbook")
    return _result_response(result)


# ---------------------------------------------------------------------------
# Allocations
# ---------------------------------------------------------------------------

@router.post(
    "/allocations",
    summary="Import Allocation Results",
    description=(
        "Upload a CSV or Excel with columns: run_id, plant_code, allocation_type, "
        "quantity_mt, unit_cost, supplier_name (optional).  "
        "Always inserts new AllocationResult rows (no dedup — per-run data)."
    ),
)
def import_allocations(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content, filename = _read_file(file)
    try:
        df = read_upload(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    result = run_import(db, AllocationImporter(), df, dataset_label="allocations")
    return _result_response(result)


# ---------------------------------------------------------------------------
# Wagons
# ---------------------------------------------------------------------------

@router.post(
    "/wagons",
    summary="Import Wagon Position Data",
    description=(
        "Upload a CSV or Excel with columns: wagon_number, status, coal_qty_mt, arrival_date (optional). "
        "Validates the schema and records."
    ),
)
def import_wagons(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content, filename = _read_file(file)
    try:
        df = read_upload(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    result = run_import(db, WagonImporter(), df, dataset_label="wagons")
    return _result_response(result)


# ---------------------------------------------------------------------------
# Import All (plants → coal-sources → constraints → landed-costs → stock → wagons)
# ---------------------------------------------------------------------------

@router.post(
    "/all",
    summary="Bulk import: plants, coal-sources, constraints, landed-costs, stock, wagons in one call",
    description=(
        "Upload a single multi-sheet Excel workbook.  Each sheet is dispatched by name:\n\n"
        "  'plants'        → PlantImporter\n"
        "  'coal_sources'  → CoalSourcesImporter\n"
        "  'constraints'   → FSAConstraintImporter\n"
        "  'landed_costs'  → LandedCostImporter\n"
        "  'stock'         → DailyStockImporter\n"
        "  'wagons'        → WagonImporter\n\n"
        "Unknown sheet names are ignored.  Results are aggregated across all sheets."
    ),
)
def import_all(
    file: UploadFile = File(..., description="Multi-sheet Excel workbook (.xlsx/.xls)"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content, filename = _read_file(file)
    if not filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The /import/all endpoint requires a multi-sheet Excel workbook (.xlsx/.xls).",
        )

    import io
    import pandas as pd

    try:
        xl = pd.ExcelFile(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to open workbook: {exc}",
        )

    sheet_importers: dict[str, tuple[type, str]] = {
        "plants": (PlantImporter, "plants"),
        "coal_sources": (CoalSourcesImporter, "coal_sources"),
        "constraints": (FSAConstraintImporter, "constraints"),
        "landed_costs": (LandedCostImporter, "landed_costs"),
        "stock": (DailyStockImporter, "stock"),
        "wagons": (WagonImporter, "wagons"),
    }

    combined = ImportResult()

    for sheet_name in xl.sheet_names:
        key = sheet_name.strip().lower().replace(" ", "_")
        if key not in sheet_importers:
            logger.info("Skipping unknown sheet '%s' in /import/all", sheet_name)
            continue

        importer_cls, label = sheet_importers[key]
        df = pd.read_excel(io.BytesIO(content), sheet_name=sheet_name, dtype=str)
        r = run_import(db, importer_cls(), df, dataset_label=label)
        combined.inserted += r.inserted
        combined.updated += r.updated
        combined.skipped += r.skipped
        combined.errors.extend(r.errors)

    return combined.to_dict()

