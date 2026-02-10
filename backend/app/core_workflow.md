# Core Workflow (Narrative)

This system is a procedural evidence workflow: it stores *facts once* and supports *many interpretations later*.

The core demo story is:

1. **A project exists**
   - A regulated scope boundary where events, evidence, and MRV reports attach.

2. **An event is recorded (fact at time-of-occurrence)**
   - The canonical “event” is an **MRV report creation**.
   - The system captures reproducibility snapshots (e.g., emission factor version/hash/value when provided).
   - An append-only **activity record** is written to represent what happened.

3. **The event is made observable (shared awareness)**
   - A notification is issued to the counterparty (typically an MRV officer for MRV report creation).
   - The counterparty can **acknowledge**, **comment**, or **dispute**.

4. **Silence becomes observed (bounded waiting)**
   - If the response window expires with no response, the system marks the event **DEEMED_OBSERVED**.
   - This is still recorded append-only, with deterministic timestamps and hashes.

5. **Verification is gated on observation**
   - The MRV workflow enforces: **SUBMITTED → VERIFIED** is blocked unless the related event is
     **ACKNOWLEDGED** or **DEEMED_OBSERVED**.
   - This prevents “verification in a vacuum”.

6. **Approval freezes interpretation**
   - Once approved, the MRV report’s compliance meaning is locked; downstream exports become reproducible.

7. **Deterministic export packages**
   - Approved/locked reports can be exported as deterministic compliance artifacts.
   - Exports include report summary, snapshots, audit trail, and acknowledgement ledger snapshots.

## DEMO API Surface

The minimal narrative orchestration endpoints live under `/api/demo/*`.

These endpoints are intentionally thin wrappers that call the existing canonical services:
- project creation → `project_service.create_project`
- MRV report creation / workflow advancement → `mrv_approval_service.*`
- acknowledgement notifications / responses → `acknowledgement_service.*`
- deterministic export → `mrv_report_export_service.build_mrv_report_export_package`

No schema changes are introduced by the demo surface.
