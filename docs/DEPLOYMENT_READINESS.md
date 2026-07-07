# Deployment Readiness Checklist

This document details the infrastructure requirements and checklist for moving the Coal Optimization & Decision Support Platform (CODSP) V1 into production.

---

## 1. Infrastructure Requirements

### Frontend Deployment
- Static web hosting environment supporting standard single-page applications (SPAs) (e.g., Nginx, Apache).
- Access to the environment variables configured at build time (e.g. `VITE_API_URL`).

### Backend Deployment
- Python 3.11 web server container or virtual machine.
- Process manager (e.g. Gunicorn with Uvicorn worker class) to manage backend execution.

### PostgreSQL Database
- PostgreSQL 14 or higher instance.
- Persistent connection pooling support.

### Persistent File Storage
- Write access to a persistent disk or volume directory mapped to the backend.
- The path must be defined in backend settings (`DOCUMENT_STORAGE_PATH`) to archive uploaded and monitor-scraped PDF files.

---

## 2. Configuration & Environment Variables

### Backend Environment Variables (.env)
Ensure the following settings are configured in the production environment:
- `DATABASE_URL`: Production PostgreSQL connection string.
- `DOCUMENT_STORAGE_PATH`: Directory path for storing archived PDFs (ensure the backend process has read/write permissions).
- `CORS_ORIGINS`: JSON-formatted list of allowed frontend domain origins.
- `SCHEDULER_ENABLED`: Set to `true` to activate the scheduler.
- `UPSLDC_MONITOR_ENABLED`: Set to `true` to active MOD report scraping (leave `false` if manual upload is preferred).
- `DOCUMENT_MAX_UPLOAD_SIZE_BYTES`: Max allowed PDF file upload limit.

---

## 3. Deployment Checklist

1. **Production CORS Alignment**:
   - Ensure the allowed CORS origins list matches the public URL of the frontend deployment.

2. **Database Migrations**:
   - Run Alembic migrations prior to starting the web app process:
     ```bash
     alembic upgrade head
     ```

3. **Database Backups**:
   - Schedule regular backups of the PostgreSQL database. Since audit logs are append-only and represent historical compliance data, their preservation is critical.

4. **Document Backup considerations**:
   - Configure backups for the local document storage directory (`storage/documents/`). If the server instance restarts or gets redeployed, this directory must remain intact on persistent storage.

5. **Single Scheduler Process Control**:
   - **Important**: The background scheduler (`APScheduler`) runs inside the web server process. To prevent duplicate scheduled tasks, the scheduler job runner must run in exactly one backend process instance. Do not scale the web process horizontally without configuring a separate dedicated scheduler runner or using a locking scheduler backend.

6. **UPSLDC Monitor Caution**:
   - Scraped PDFs are saved automatically to `storage/documents/variable_cost_pdf/` and registered under document metadata.
   - Monitor activity is audited. Ensure the server has outbound internet access to target `https://www.upsldc.org/schmod`.

7. **Health Checks**:
   - Configure load balancers or monitoring services to ping `/health`. This endpoint verifies database connectivity and returns HTTP 200 on success.
