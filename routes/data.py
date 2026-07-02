"""
routes/data.py
Read-only endpoints that serve the JSON data files on disk.
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from config import DATA_DIR

router = APIRouter(prefix="/api/data", tags=["Data Files"])


def _load(filename: str):
    path: Path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"'{filename}' not found in data directory.")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"JSON parse error in '{filename}': {exc}")


@router.get("/constraints", summary="ACQ & Bridge Linkage constraints registry")
def get_constraints():
    """Returns the full constraints_registry.json (FSA + Bridge Linkage ACQ caps)."""
    return _load("constraints_registry.json")


@router.get("/costs", summary="Landed cost dynamics per plant/company")
def get_costs():
    """Returns cost_inputs.json (landed cost, GCV, variable cost per plant/company)."""
    return _load("cost_inputs.json")


@router.get("/daily-fuel", summary="Daily fuel position report")
def get_daily_fuel():
    """Returns daily_fuel.json (stock, receipt, consumption, generation per plant)."""
    return _load("daily_fuel.json")


@router.get("/optimization-run", summary="Last saved optimisation result")
def get_optimization_run():
    """Returns optimization_run.json — the most recently saved LP run."""
    return _load("optimization_run.json")


@router.get("/snapshot", summary="Combined frontend snapshot")
def get_snapshot():
    """
    Aggregates constraints, daily_fuel and the last optimisation run into the
    single JSON format expected by the React frontend (matching demoSnapshot.json).
    """
    from optimizer import run_optimisation, save_json

    constraints = _load("constraints_registry.json")
    daily_fuel  = _load("daily_fuel.json")
    try:
        optimization = _load("optimization_run.json")
    except HTTPException:
        optimization = run_optimisation()
        save_json("optimization_run.json", optimization)

    return {
        "optimization":   optimization,
        "daily_fuel":     daily_fuel,
        "constraints":    constraints,
        "generated_from": "FastAPI Dynamic Server",
    }
