# Demo Walkthrough (5 Minutes)

This is a **5-minute, pilot-friendly** walkthrough of the seeded demo data. It is designed for LOI / evaluation settings where you need to show reproducibility, traceability, and explainability **without making any compliance claims**.

In `DEMO_MODE=true` the backend:
- Seeds synthetic (demo) projects/reports.
- Blocks non-demo-safe write actions (you can browse, upload demo evidence, run read-only anomaly checks, and export watermarked bundles).
- Watermarks exports and demo evidence so they can’t be mistaken for real compliance artifacts.

The backend also exposes a read-only helper endpoint you can use to confirm the scripted step order:
- `GET /api/v1/demo/walkthrough-state`

## Start the demo stack

PowerShell:

`$env:DEMO_MODE="true"; docker compose up -d --build`

Sanity check:
- `GET http://localhost:8000/health` should return `{"status":"ok","db":true,...}` and include `"mode":"demo"`
- Frontend: `http://localhost:3000` (Docker) or `http://localhost:5173` (local Vite)

## Accounts to log in

Use one account for the full walkthrough unless you explicitly want to demonstrate separation-of-duties roles.

Recommended (single-login demo):
- Admin: `admin@example.com` / `Admin123!`

Optional (role narration):
- MRV Officer (Verifier): `verifier@example.com` / `verifier123`
- Project Manager: `pm@example.com` / `PM123456!`
- Supplier: `supplier@example.com` / `Supply789!`

## Walkthrough steps (exact order)

### 1) Login

What to click:
- Open `http://localhost:5173`
- Enter the Admin demo credentials

Screenshot placeholder:
- `[Screenshot: Login screen]`

What to explain verbally:
- “This is a regulator-grade MRV demo posture: demo data is synthetic, and sensitive write actions are blocked. We can still view the full audit trail and export bundle.”

### 2) View seeded project

What to click:
- In the left nav, open **Projects**
- Select the project whose name starts with `DEMO` (example seeded name: “DEMO – Green Concrete Pilot”)

Screenshot placeholder:
- `[Screenshot: Project list with DEMO project highlighted]`

### 3) Open dashboard KPIs

What to click:
- Return to the **Dashboard** view
- Point at the KPI cards (Active Projects, CO₂ Saved, Open Anomalies, etc.)
- Click “What am I seeing?” (opens a read-only explanation modal)

What to explain verbally:
- “These KPIs are aggregated indicators from immutable records (projects, MRV reports, evidence hashes, anomalies).”
- “In Demo/Pilot mode, this is illustrative and explicitly labeled as **not a compliance claim**.”

Screenshot placeholder:
- `[Screenshot: KPI cards + 'Not a Compliance Claim' badge]`

What to explain verbally:
- “This project is pre-seeded to ensure the dashboard is non-zero and consistent for evaluation.”
- “The data model is PostgreSQL-backed with async SQLAlchemy and Alembic migrations (no SQLite-in-production patterns).”

### 4) View MRV lifecycle (draft → approved)

What to click:
- Open **MRV**
- View the MRV list/queue and open a seeded report
- Point out the status progression shown for reports (draft/submitted/verified/approved as present in the seeded set)

Screenshot placeholder:
- `[Screenshot: MRV report list showing multiple statuses]`

What to explain verbally:
- “This is the lifecycle we use for verification governance: draft → verified → approved. In demo mode, we’re showing the lifecycle states on seeded records without allowing risky mutations.”
- “Each calculation stores an emission-factor snapshot (version/hash/value) to support reproducibility.”

### 5) View emission factor snapshot

What to click:
- On the **MRV** report view, locate:
  - Emission Factor Version
  - Emission Factor Value
  - Emission Factor Hash
- Also point to **Company Overview** where emission-factor sources are summarized

What to explain verbally:
- “We don’t just store a number—we store the versioned emission factor snapshot used at calculation time. That’s what makes results reproducible and audit-friendly.”

Screenshot placeholder:
- `[Screenshot: Emission factor snapshot fields]`

### 6) View audit log (append-only)

What to click:
- Open **Audit Log**
- Filter/scroll to an MRV report event (create/submit/verify) or evidence upload event

What to explain verbally:
- “Audit logs are append-only and chained so edits are detectable.”
- “This is the basis for regulator-grade traceability in a pilot.”

Screenshot placeholder:
- `[Screenshot: Audit log table with MRV events]`

### 7) Trigger anomaly check (read-only)

What to click:
- Open **Anomalies**
- Trigger an anomaly check for a seeded demo token (the demo seed includes a token intended to trigger a deterministic rule)

What to explain verbally:
- “Anomaly checks are deterministic and explainable.”
- “In DEMO mode, anomaly checks are **read-only**: results are returned but not persisted as real audit events.”

Screenshot placeholder:
- `[Screenshot: Anomaly check result view]`

### 8) View anomaly explanation

What to click:
- Open **Anomalies**
- Select a project and review the anomaly table
- Point to the **Explanation** column (rule-based, deterministic text)

What to explain verbally:
- “Anomalies are explainable: each flagged event has a human-readable rationale and a rule identifier.”
- “In demo mode, anomaly operations are constrained to seeded DEMO records only.”

### 9) Export MRV bundle (watermarked)

What to click:
- Open the MRV report list
- For an APPROVED/LOCKED report, click **Export Compliance Bundle**

What to explain verbally:
- “This generates a review-ready bundle (ZIP) with structured artifacts for external review.”
- “In demo mode and pilot-tagged records, exports are explicitly watermarked to prevent accidental misuse as a compliance claim.”

Screenshot placeholder:
- `[Screenshot: Export button + downloaded ZIP filename]`

## Optional: evidence upload (sandboxed)

If you need to show evidence handling, keep it clearly framed as a sandbox.

Constraints in demo mode:
- Only `/api/v1/upload/evidence` is permitted for uploads.
- Uploads must attach to a `DEMO` project record (by `report_id` or `token_uid`).
- Uploads must be tagged `demo=true` and are stored under `demo_uploads/`.

Example (curl; replace placeholders from what you see in the UI/API):
`curl -X POST "http://localhost:8000/api/v1/upload/evidence?report_id=<REPORT_ID>&evidence_kind=invoice&demo=true" -H "Authorization: Bearer <TOKEN>" -F "file=@sample.pdf"`
