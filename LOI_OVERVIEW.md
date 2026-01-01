# LOI Overview (Pilot-Focused)

## What problem this solves
Construction teams increasingly want to purchase and use **lower-carbon materials** (e.g., cement, steel, aggregates), but today it is hard to verify claims consistently across suppliers and projects. Evidence is often scattered across PDFs, emails, and spreadsheets, and it’s difficult to prove:

- what was delivered,
- to which project/site,
- under which methodology and emission factor,
- and whether the calculation can be reproduced later.

## Why current systems fail
Most systems used today are:

- **Manual**: evidence collection and calculations are spreadsheet-driven.
- **Unverifiable**: there’s no consistent evidence hash chain or immutable audit trail.
- **Not reproducible**: emission factors and assumptions drift over time; re-running a report later yields a different answer.
- **Hard to audit**: reviewers cannot quickly validate “what changed” and “who approved what”.

## How this system helps
This MRV system is designed to be regulator-grade in architecture (immutability, versioned inputs, auditability), while remaining pilot-friendly.

### Green material producers
- Provide structured, hash-linked evidence that can be attached to deliveries and MRV reports.
- Make reviews faster by packaging a consistent “compliance bundle” for each MRV report.

### Governments and public owners
- Review projects using consistent rules and an immutable audit trail.
- Compare projects using aggregated KPIs without exposing sensitive raw evidence.

### Contractors and project teams
- Track projects and MRV reports in a clear lifecycle (draft → submitted → verified → approved/locked).
- Produce deterministic exports for third-party review.

## Why it’s pilot-ready
This is not a legal claim or credit issuance system. In pilot posture:

- Demo/pilot data is **explicitly labeled** as non-claim.
- Exports are **watermarked** in demo/pilot contexts.
- The core workflow is present so stakeholders can evaluate auditability and reproducibility.

## What an LOI would enable
An LOI would enable a joint pilot where stakeholders can:

- validate the workflow against real operating needs,
- define what evidence is required for different materials,
- tune anomaly rules and review roles,
- and refine report/export formats for reviewers.

The goal is to learn quickly, harden the system based on feedback, and prepare for a scoped pilot with clear boundaries.
