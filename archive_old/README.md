# Archived non-canonical backends

This repository intentionally maintains **one canonical execution backend**:

- `backend/` (FastAPI + async SQLAlchemy + PostgreSQL + Alembic)

Everything else in this folder is **archived** to reduce ambiguity and prevent accidental execution against non-compliant prototypes.

## Inventory (what existed before archiving)

- `app/` (root)
  - FastAPI routers (`app/api/*`), its own DB/session/config layout.
  - Overlaps with canonical backend concepts but is not the regulator-grade backend.

- `prototype/backend/`
  - Minimal FastAPI prototype skeleton.
  - Not used for canonical execution.

- `sustainable_city_poc/backend/`
  - POC backend artifacts (models/db/migrations-like structure).
  - Not used for canonical execution.

## Why archive?

- The system constitution lives in `SYSTEM_RULES.md` and is implemented/enforced in `backend/`.
- Multiple backends create ambiguity for compliance, auditability, and reproducibility.
- Archiving keeps history and reference material without letting it drift into production paths.

## How to run

- Backend: `cd backend && uvicorn app.main:app --reload`
- Frontend: `cd frontend && npm run dev`
