"""
config.py
Loads all environment variables from .env using python-dotenv.
All other modules import settings from here.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# ── Server ─────────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
API_PORT: int = int(os.getenv("API_PORT", "8000"))

# ── MongoDB ─────────────────────────────────────────────────────────────────
MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "uprvunl_coal")

# ── Supabase (optional, used by edge-functions / React frontend) ─────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# ── Anthropic (optional, used by extract-fsa edge function) ─────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

# ── Local data directory (JSON files) ────────────────────────────────────────
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"
