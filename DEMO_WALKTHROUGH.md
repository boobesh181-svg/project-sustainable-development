# Demo Walkthrough (LOI Pilot)

This system supports **regulator-grade MRV** for sustainable construction. In `DEMO_MODE`, it seeds synthetic data, blocks most write operations, and **watermarks exports** as demo.

## 1) Start the demo stack

- Run (PowerShell):

`$env:DEMO_MODE="true"; docker compose up -d --build`

- Verify backend:

`GET http://localhost:8000/health`

Expected:
- `{"status":"ok","db":true,"demo_mode":true,...}`

- Open frontend:

`http://localhost:5173`

## 2) Log in with demo users

Use any of these pre-seeded accounts:

- Admin: `admin@example.com` / `Admin123!`
- MRV Officer (Verifier): `verifier@example.com` / `verifier123`
- Project Manager: `pm@example.com` / `PM123456!`
- Supplier: `supplier@example.com` / `Supply789!`

## 3) What to click (5 minutes)

1. **Company Overview**
   - First screen after login.
   - Shows seeded project + KPIs.

2. **Anomalies (Explainability demo)**
   - View anomaly table and deterministic explanations.
   - Use the UI control to run anomaly checks if available.

3. **Compliance Export (ISO package)**
   - Click **Download Compliance Package**.
   - Output is a ZIP with JSON + CSVs, and includes **demo watermark fields**.

## 4) Demo evidence uploads (sandboxed)

In demo mode, only `/api/v1/upload/evidence` is permitted for uploads.

Rules:
- Upload must attach to a **DEMO project** via either `report_id` or `token_uid`.
- The created Evidence row is auto-tagged:
  - `demo_only=true`
  - `non_compliant=true`

Example (curl; replace `<REPORT_ID>` with a seeded report id you see in the UI/API):

`curl -X POST "http://localhost:8000/api/v1/upload/evidence?report_id=<REPORT_ID>&evidence_kind=invoice" -H "Authorization: Bearer <TOKEN>" -F "file=@sample.pdf"`

## 5) Demo MRV advancement (seeded-only)

In demo mode, advancing MRV status is allowed **only** for seeded DEMO reports:

`POST /api/v1/mrv-approval/reports/{report_id}/advance`

Non-demo projects/reports remain locked by demo safety controls.

## Notes

- Demo uploads and workflow actions are intentionally constrained to avoid any accidental mutation of compliance-relevant data.
- Demo data is synthetic and **not** a real compliance claim.
