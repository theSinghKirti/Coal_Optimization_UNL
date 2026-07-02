"""
routes/optimization.py
Endpoints that trigger and manage LP optimisation runs.
"""
from fastapi import APIRouter, HTTPException
from models import OptimizationRequest, OptimizationResult
from optimizer import run_optimisation, save_json

router = APIRouter(prefix="/api/optimization", tags=["Optimisation"])


@router.get(
    "/run",
    response_model=OptimizationResult,
    summary="Run LP optimisation (saves result to disk)",
)
def run_and_save():
    """
    Executes the coal allocation LP using the current data files,
    persists the result to data/optimization_run.json, and returns it.
    """
    try:
        result = run_optimisation()
        save_json("optimization_run.json", result)
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Optimisation failed: {exc}")


@router.post(
    "/run-dynamic",
    response_model=OptimizationResult,
    summary="Run LP with custom demand / premium (result not saved)",
)
def run_dynamic(req: OptimizationRequest):
    """
    Executes the LP with optional per-plant demand overrides and a custom
    market-premium multiplier.  Result is returned but **not** written to disk,
    so the baseline saved run is preserved.
    """
    try:
        return run_optimisation(
            custom_demands=req.custom_demands,
            market_premium=req.market_premium,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dynamic optimisation failed: {exc}")
