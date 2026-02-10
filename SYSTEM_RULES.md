# InfraSentinel — System Rules (Constitution)

This document defines the non-negotiable behavioral rules of the system.
All code, database schema, APIs, and UI must comply with these rules.

If a requested feature conflicts with this document, the system must reject the feature — not silently adapt.

InfraSentinel is an evidence workflow system, not a calculator.

---

## 1. Core Principle

The system stores historical facts once and interprets them many times.

Facts are immutable.
Interpretations are reproducible and versioned.

---

## 2. Activity Record Rules

1. An activity record represents a real-world occurrence.
2. After verification, an activity record can never be edited.
3. Corrections must create a new record referencing the previous record.
4. Deleting approved historical records is forbidden.
5. Every record must contain timestamp, actor, and project boundary.

---

## 3. Evidence Rules

1. Evidence files are identified by cryptographic hash.
2. If file content changes, it is a new evidence record.
3. Evidence cannot be replaced after approval.
4. Evidence can only be appended.
5. The system never stores “latest file” — only versioned files.

---

## 4. Acknowledgement Rules

1. Recording an activity must notify a counterparty.
2. Counterparty has a defined response window.
3. No response within window = deemed observed.
4. Acknowledgement does not equal acceptance.
5. Responses are append-only and cannot be edited.

---

## 5. Approval Rules

1. Creator, verifier, and approver must be different users.
2. Approval freezes the historical snapshot, not future interpretations.
3. Approval never deletes previous states.
4. Locked records cannot be modified.
5. Reopening requires creating a new version, not editing.

---

## 6. Calculation Rules

1. Emissions are derived from quantity × factor version.
2. The factor version used during approval must be preserved forever.
3. New methodology versions must create new report outputs.
4. Reports must be reproducible at any future time.
5. Stored emissions are snapshots, not permanent truth.

---

## 7. Organizational Boundary Rules

1. The system stores relationships, not emission ownership.
2. Scope classification must be derived at reporting time.
3. Multiple organizations may generate different reports from the same events.
4. Changing ownership must not alter historical activity data.
5. Reports must specify boundary method used.

---

## 8. Audit Trail Rules

1. All important actions create an audit event.
2. Audit events are append-only.
3. Past audit records cannot be altered.
4. The system must detect tampering attempts.
5. Audit history is part of the evidence.

---

## 9. Recalculation Rules

1. Historical records remain unchanged during recalculation.
2. New interpretations create new report versions.
3. Emission factor updates do not modify old approvals.
4. Structural ownership changes affect reports, not events.
5. The system must support multiple valid totals over time.

---

## 10. System Safety Rules

1. The system must refuse operations that break these rules.
2. UI restrictions are insufficient — backend must enforce rules.
3. Demo mode must never create real compliance artifacts.
4. Exported reports must include context metadata.
5. The system prioritizes integrity over convenience.

---

## Final Statement

InfraSentinel is a procedural evidence system.

It does not guarantee correctness of the real world.
It guarantees that recorded history cannot be silently rewritten and can be reinterpreted transparently.

All implementations must preserve this property.
