# CODSP — Frontend/Backend Integration Phase 0 Report

> **Scope:** Connectivity setup only. No demo data replaced, no UI changed, no form wiring started.
> **Date:** 2026-07-06

---

## Files Changed

### Backend

| File | Change |
|---|---|
| `backend/app/core/config.py` | Added `allowed_origins: str` field (reads `ALLOWED_ORIGINS` env var; comma-separated; defaults to local Vite ports) |
| `backend/app/main.py` | Added `CORSMiddleware` import + `app.add_middleware(...)` block that parses `settings.allowed_origins` at startup |
| `backend/.env.example` | Added `ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173` with explanatory comment |

### Frontend

| File | Change |
|---|---|
| `frontend/.env.example` | Created with `VITE_API_BASE_URL=http://127.0.0.1:8001` and Supabase commented stubs |
| `frontend/src/lib/api.js` | Created shared API config module (see details below) |

**No existing files were deleted or modified outside the above list.**
**demoSnapshot.json, Supabase client, legacy API_BASE constants, all components — all untouched.**

---

## Environment Variables Added

### Backend (add to `backend/.env`)

```env
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

- Type: comma-separated string
- Default if absent: `http://localhost:5173,http://127.0.0.1:5173`
- For production: append your deployed frontend domain, e.g. `https://codsp.uprvunl.gov.in`

### Frontend (create `frontend/.env` from `.env.example`)

```env
VITE_API_BASE_URL=http://127.0.0.1:8001
```

- Read by `src/lib/api.js` at build time via `import.meta.env.VITE_API_BASE_URL`
- Fallback if absent: `http://127.0.0.1:8001/api/v1` (hard-coded inside `api.js`)
- Must include `/api/v1` prefix if overriding the default

---

## CORS Configuration Summary

**Middleware:** `fastapi.middleware.cors.CORSMiddleware` (from Starlette, bundled with FastAPI — no new package added)

**Location:** `backend/app/main.py`, after `register_exception_handlers(app)`, before router mounting

**Configuration:**

```python
_cors_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,   # explicit list, never wildcard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Allowed origins (default):**
- `http://localhost:5173` — Vite dev server
- `http://127.0.0.1:5173` — alternative Vite local address

**Security note:** No wildcard (`*`) is used for origins, even in development. Production URLs must be explicitly added to `ALLOWED_ORIGINS`.

---

## Frontend `api.js` Module Summary

**Location:** `frontend/src/lib/api.js`

**Exports:**

| Export | Type | Description |
|---|---|---|
| `apiBase` | `string` | Normalized base URL (VITE_API_BASE_URL, trailing slash stripped) |
| `apiUrl(path)` | `function` | Builds full URL by appending path to `apiBase` |
| `checkHealth()` | `async function` | Calls `GET /api/v1/health`, returns `{ status, database }` |

**Not wired into any dashboard component.** Existing components retain their own `API_BASE` constants and continue to use `demoSnapshot.json` as-is. This module is the foundation for Phase 1 wiring only.

---

## Health-Check Verification

**Method:** Python import check (PostgreSQL not required for config verification)

```
allowed_origins: 'http://localhost:5173,http://127.0.0.1:5173'
parsed list: ['http://localhost:5173', 'http://127.0.0.1:5173']
```

Settings load correctly. The CORS origin list is populated at startup from the env var default.

**To verify end-to-end from a browser console** (once backend is running on 8001):
```js
import { checkHealth } from "./src/lib/api.js";
checkHealth().then(console.log);
// Expected: { status: "ok", database: "ok" }
```

Or from the browser dev console while Vite dev server is running:
```js
fetch("http://127.0.0.1:8001/api/v1/health", { headers: { Origin: "http://localhost:5173" } })
  .then(r => r.json()).then(console.log);
// Expected: { "status": "ok", "database": "ok" }
// Expected response headers: Access-Control-Allow-Origin: http://localhost:5173
```

---

## Test Results

### Backend ruff check

```
ruff check backend/
All checks passed!
```

### Backend pytest

```
45 passed in 7.72s
```

All 45 existing tests pass. No tests were added or removed.

### Frontend build

```
npm run build (from frontend/)

vite v5.4.21 building for production...
841 modules transformed.
dist/index.html          0.49 kB
dist/assets/index.css   21.83 kB
dist/assets/index.js   624.42 kB
Built in 4.59s
```

Build succeeds cleanly. The chunk-size warning is pre-existing (not caused by this change).

---

## Commands to Start Locally

### Start the backend (port 8001)

```powershell
# From workspace root: c:\Users\itisa\Desktop\mdsir\
# Activate the virtualenv
.\.venv\Scripts\Activate.ps1

# Run FastAPI on port 8001
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload --app-dir backend
```

Or, from inside the backend directory:

```powershell
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Verify backend is alive:
```
GET http://127.0.0.1:8001/api/v1/health
Expected: {"status":"ok","database":"ok"}
```

### Start the frontend (port 5173)

```powershell
# From workspace root:
cd frontend
npm run dev
```

Vite will start at http://localhost:5173 by default.

### Copy the frontend env file

```powershell
# From frontend/ directory:
Copy-Item .env.example .env
```

This sets `VITE_API_BASE_URL=http://127.0.0.1:8001` which `api.js` will read.

---

## Demo Dashboard Data Status

**demoSnapshot.json has NOT been replaced or modified.**

- `src/data/demoSnapshot.json` — unchanged
- `src/App.jsx` — unchanged (still imports and uses snapshot as state default)
- All 9 dashboard tabs — unchanged
- All existing forms — unchanged
- Supabase client — unchanged (still dormant)

The dashboard loads and displays demo data exactly as before. The only new capability is that `frontend/src/lib/api.js` is available as a ready-to-use module for Phase 1 wiring.

---

## What Is NOT Done (Deferred to Phase 1+)

- [ ] Replace `demoSnapshot.json` with live API calls
- [ ] Remap legacy `API_BASE` constants in 6 component files to use `api.js`
- [ ] Wire `FuelPositionTab`, `RegistryTab`, `AuditLogTab` to real endpoints
- [ ] Wire `DailyFuelForm` POST to `/api/v1/daily-stock`
- [ ] Build plant UUID lookup for form submissions
- [ ] Remap optimization trigger button to POST
- [ ] Connect `DocumentCenterTab` list + upload
