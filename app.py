"""
app.py
UPRVUNL Coal Optimization — FastAPI entry point.

Startup:
    python app.py                              # direct
    uvicorn app:app --reload                   # dev (hot-reload)
    venv\\Scripts\\python -m uvicorn app:app    # Windows venv

Docs:  http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from config import API_HOST, API_PORT
from database import close_client
from routes.data import router as data_router
from routes.optimization import router as optimization_router
from routes.mongo import router as mongo_router

# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="UPRVUNL Coal Optimization API",
    description=(
        "Backend API for UPRVUNL's coal source allocation optimization. "
        "Provides LP-based cost minimisation, operational data access, "
        "and MongoDB-backed CRUD for daily fuel and constraint records."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS (allow React frontend on any port during development) ─────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(data_router)
app.include_router(optimization_router)
app.include_router(mongo_router)

# ── Lifecycle ─────────────────────────────────────────────────────────────────

@app.on_event("shutdown")
def on_shutdown():
    close_client()

# ── Root redirect ─────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse(url="/docs")

# ── Dev runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=API_HOST, port=API_PORT, reload=True)
