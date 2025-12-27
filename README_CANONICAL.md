# Canonical MRV System (Regulator-Grade)

This repository uses **/backend** as the single canonical execution backend.
All other backends (e.g. `/app`, `/prototype`, `/sustainable_city_poc`) are **deprecated** and must not be executed.

## What You Get

- **Backend**: FastAPI + async SQLAlchemy + PostgreSQL + Alembic migrations
- **Frontend**: React + TypeScript + Vite (dashboard-only UI)
- **Compliance primitives**: strict MRV workflow, separation-of-duties, immutable-after-approval/verification controls, append-only audit logs

## Quick Start (Docker)

From the repo root:

```bash
docker compose up --build -d
```

Health checks:

- Backend: `http://localhost:8000/health`
- Frontend (dev): `http://localhost:5173`

## Quick Start (Local Dev)

### Backend

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_dashboard.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

The frontend uses the Vite proxy and calls the backend via relative `/api` URLs.

## Demo Accounts (Seeded)

After running `python backend/scripts/seed_dashboard.py`, these demo accounts exist:

- **Admin**: `admin@example.com` / `Admin123!`
- **Approver (Admin)**: `approver@example.com` / `approver123`
- **Verifier (MRV Officer)**: `verifier@example.com` / `verifier123`
- **Contractor**: `contractor@example.com` / `Contract789!`
- **Project Manager**: `pm@example.com` / `PM123456!`
- **Supplier**: `supplier@example.com` / `Supply789!`
- **Citizen**: `citizen@example.com` / `Citizen123!`

## MRV Approval Workflow

The canonical MRV approval API is under:

- `GET /api/v1/mrv-approval/reports`
- `POST /api/v1/mrv-approval/reports` (create DRAFT; contractor/project_manager)
- `POST /api/v1/mrv-approval/reports/{report_id}/advance` (strict progression)

State machine:

- `DRAFT → SUBMITTED` (creator submits)
- `SUBMITTED → VERIFIED` (MRV Officer verifies; must differ from creator)
- `VERIFIED → APPROVED` (Admin approves; must differ from creator and verifier)
- `APPROVED → LOCKED` (Admin locks; final immutable)

The frontend home page reflects these role-based actions.

## Notes

- PostgreSQL is required for canonical operation (SQLite is not supported for production-grade compliance).
- Every schema change requires a new Alembic migration (no editing applied history).
