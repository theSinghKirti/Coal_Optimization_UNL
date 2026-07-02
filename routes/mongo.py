"""
routes/mongo.py
CRUD endpoints backed by MongoDB collections.
All collections are accessed through database.py helpers.
"""
from datetime import datetime, timezone
from typing import List

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from models import DailyFuelEntry, ConstraintEntry
from database import col_daily_fuel, col_constraints, col_optimization_runs

router = APIRouter(prefix="/api/mongo", tags=["MongoDB"])


def _serialize(doc: dict) -> dict:
    """Convert ObjectId to string so FastAPI can JSON-encode it."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


# ── Daily Fuel ────────────────────────────────────────────────────────────────

@router.get("/daily-fuel", summary="Fetch all daily-fuel records from MongoDB")
def mongo_list_daily_fuel():
    docs = [_serialize(d) for d in col_daily_fuel().find({}, {"_id": 1, "plant": 1,
            "report_date": 1, "fuel_type": 1, "closing_balance": 1,
            "days_stock_cover": 1, "generation_mu": 1})]
    return docs


@router.post("/daily-fuel", status_code=201, summary="Insert a daily-fuel record into MongoDB")
def mongo_insert_daily_fuel(entry: DailyFuelEntry):
    doc = entry.model_dump()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    result = col_daily_fuel().insert_one(doc)
    return {"inserted_id": str(result.inserted_id)}


# ── Constraints ───────────────────────────────────────────────────────────────

@router.get("/constraints", summary="Fetch all constraint records from MongoDB")
def mongo_list_constraints():
    return [_serialize(d) for d in col_constraints().find()]


@router.post("/constraints", status_code=201, summary="Insert a constraint record into MongoDB")
def mongo_insert_constraint(entry: ConstraintEntry):
    doc = entry.model_dump()
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    result = col_constraints().insert_one(doc)
    return {"inserted_id": str(result.inserted_id)}


# ── Optimisation Run History ──────────────────────────────────────────────────

@router.get("/optimization-runs", summary="List optimisation run history from MongoDB")
def mongo_list_runs():
    docs = list(col_optimization_runs().find(
        {},
        {"_id": 1, "status": 1, "total_optimized_cost_rs": 1,
         "estimated_savings_rs": 1, "saved_at": 1}
    ))
    return [_serialize(d) for d in docs]


@router.post("/optimization-runs", status_code=201,
             summary="Save an optimisation result to MongoDB history")
def mongo_save_run(result: dict):
    result["saved_at"] = datetime.now(timezone.utc).isoformat()
    inserted = col_optimization_runs().insert_one(result)
    return {"inserted_id": str(inserted.inserted_id)}
