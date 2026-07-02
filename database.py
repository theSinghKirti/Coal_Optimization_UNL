"""
database.py
MongoDB connection singleton using pymongo.
All route modules import `db` from here.
"""
from pymongo import MongoClient
from pymongo.database import Database
from config import MONGODB_URI, MONGODB_DB_NAME

_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Return the shared MongoClient, creating it on first call."""
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_db() -> Database:
    """Return the application database."""
    return get_client()[MONGODB_DB_NAME]


def close_client():
    """Close the MongoDB connection (call on app shutdown)."""
    global _client
    if _client:
        _client.close()
        _client = None


# ── Collection helpers ────────────────────────────────────────────────────────

def col_optimization_runs():
    return get_db()["optimization_runs"]


def col_daily_fuel():
    return get_db()["daily_fuel"]


def col_constraints():
    return get_db()["constraints"]


def col_costs():
    return get_db()["cost_inputs"]
