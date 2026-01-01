# LOI Readiness Checklist

This checklist is meant to help a partner quickly understand what is **implemented today**, what is **simulated for demo**, and what is **planned post-pilot**.

## What is implemented
- Docker-based stack runnable via `docker compose up`.
- Regulator-grade architecture patterns:
  - PostgreSQL-backed persistence.
  - Alembic migrations.
  - Immutable lifecycle constraints and append-only audit logging (DB-level enforcement remains in place).
- Demo posture:
  - `DEMO_MODE=true` enables safe demo constraints and seeded demo data.
  - Non-demo-safe write actions are blocked with a clear error message.
  - Demo evidence is sandboxed and watermarked.
- Dashboard:
  - KPI summary and chart endpoints.
  - Public metrics endpoint is aggregate-only.
- MRV exports:
  - Deterministic per-report export bundle.
  - Watermarking in demo mode and for pilot-tagged records.

## What is simulated (for demo)
- Seeded demo projects and MRV reports are synthetic and labeled as pilot/demo.
- Anomaly checks in demo mode are run in a read-only posture (results returned without producing new immutable audit records).

## What is planned post-pilot
- Refinement of evidence requirements per material type (templates, validation rules).
- Expanded review workflows and reporting formats based on reviewer feedback.
- Optional performance hardening and pre-aggregation once real pilot scale is known.

## What companies are NOT responsible for yet
- No external integrations are required (no IoT, satellite, blockchain).
- No requirement to issue or retire credits.
- No requirement to integrate with ERP systems.
- No obligation to treat pilot data as a compliance claim.

## Operator quick checks
- Backend health: `GET /health` returns `{ "status": "ok", "db": true, ... }`.
- Demo mode: set `DEMO_MODE=true` and confirm the UI shows “Demo Mode” and “Not a Compliance Claim”.
- Export watermark: export a seeded MRV report bundle and verify a `DEMO_NOTICE.txt` or `PILOT_NOTICE.txt` file exists in the ZIP.
