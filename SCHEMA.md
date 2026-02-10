# Canonical Schema (Regulator-Grade)

This document describes the **canonical execution backend** schema implemented in `backend/`.

Principles:
- **Append-only / immutability** for audit-critical entities (enforced via PostgreSQL triggers).
- **ISO-14064 reproducibility** via snapshotted calculation inputs (hashes + version identifiers).
- **Separation of duties**: issuer/verifier/approver roles must be distinct where applicable.
- **PostgreSQL only**; async SQLAlchemy 2.0; Alembic migrations required for schema changes.

## Core entities

## Identity & Access

- `role`
  - `id` (PK)
  - `name` (enum-like, e.g. `admin`, `mrv_officer`, `contractor`, `supplier`)

- `user`
  - `id` (UUID PK)
  - `email` (unique)
  - `hashed_password`
  - `full_name`
  - `is_active`
  - `role_id` → `role.id`
  - `supplier_id` (nullable) → `supplier.id`
  - `created_at`, `updated_at`

## Projects

- `project`
  - `id` (UUID PK)
  - `name`
  - `status`
  - `lat`, `lon`
  - `budget_usd`
  - `created_by` → `user.id`
  - `created_at`, `updated_at`

## Emission factor governance

- `emission_factor` (immutable once activated)
  - `id` (UUID PK)
  - `material_code`, `material_name`
  - `version` (per `material_code`)
  - `co2e_per_unit` (Numeric(18,6))
  - `unit` (e.g. kg/ton/m3)
  - `source_type`, `jurisdiction`, `methodology_reference`
  - `valid_from`, `valid_to`
  - `factor_hash` (SHA-256, unique)
  - `is_active` (once True: UPDATE/DELETE blocked by trigger)
  - `created_at`, `created_by`, `created_by_user_id`

## Materials & deliveries

- `supplier`
  - `id` (UUID PK)
  - `name`
  - `partnership_discount`
  - `total_value_supplied`

- `material_token`
  - `id` (UUID PK)
  - `project_id` → `project.id`
  - `supplier_id` (nullable/required by constraints in redemption workflows) → `supplier.id`
  - `material_code`, `material_name`
  - `quantity`, `unit`
  - `token_uid` (unique)
  - `issued_by`
  - `redeemed` (bool) + redemption metadata
  - evidence fields: `delivery_photo_path`, `delivery_lat`, `delivery_lon`, `supplier_invoice_ref`, `delivery_timestamp`
  - `created_at`, `updated_at`

- `delivery_verification` (immutable after approval)
  - `id` (UUID PK)
  - `material_token_id` → `material_token.id`
  - evidence integrity fingerprints/hashes
  - `verified_at`, `verified_by_user_id`
  - `is_verified` (bool)

## MRV workflow

- `mrv_report`
  - `id` (UUID PK)
  - `project_id` → `project.id`
  - `reporting_period`
  - `sample_desc`, `parameter`, `value`
  - `total_co2e` (Numeric(18,6))
  - `emission_factor_id` (nullable) → `emission_factor.id`
  - snapshot fields for reproducibility:
    - `emission_factor_version_snapshot`
    - `emission_factor_hash_snapshot`
    - `emission_factor_value_snapshot`
  - `status` (DRAFT → SUBMITTED → VERIFIED → APPROVED → LOCKED)
  - `created_by`, `verified_by`, `approved_by` → `user.id`
  - separation-of-duties CHECK constraints: creator ≠ verifier ≠ approver
  - `created_at`, `updated_at`

## Append-only acknowledgement layer

These tables store *facts once* (activity) and then attach notifications/responses. Derived status is stored as an append-only ledger.

- `activity_record` (append-only)
  - `id` (UUID PK)
  - `activity_type` (e.g. `MATERIAL_TOKEN_REDEEMED`, `DELIVERY_VERIFICATION_CREATED`, `MRV_REPORT_CREATED`)
  - `project_id` → `project.id`
  - exactly one of:
    - `material_token_id` → `material_token.id`
    - `delivery_verification_id` → `delivery_verification.id`
    - `mrv_report_id` → `mrv_report.id`
  - `occurred_at`
  - `created_by_user_id` (nullable) → `user.id`
  - `activity_hash` (SHA-256, unique)
  - DB trigger blocks UPDATE/DELETE

- `event_notification` (append-only)
  - `id` (UUID PK)
  - `activity_id` → `activity_record.id`
  - `notified_user_id` → `user.id`
  - `notification_timestamp`, `response_deadline_timestamp`
  - `delivery_channel`
  - `notification_hash` (SHA-256, unique)
  - DB trigger blocks UPDATE/DELETE

- `event_response` (append-only)
  - `id` (UUID PK)
  - `notification_id` → `event_notification.id`
  - `responder_user_id` → `user.id`
  - `response_type` (ACKNOWLEDGED / DISPUTED / COMMENTED / NO_RESPONSE_AUTO)
  - `response_timestamp`
  - `response_comment` (nullable)
  - `response_hash` (SHA-256, unique)
  - DB trigger blocks UPDATE/DELETE

- `event_status_ledger` (append-only derived status)
  - `id` (UUID PK)
  - `activity_id` → `activity_record.id`
  - `derived_status` (UNSEEN / SEEN / ACKNOWLEDGED / DISPUTED / DEEMED_OBSERVED)
  - `computed_at`
  - `computation_basis_hash` (SHA-256, unique)

## Audit log

- `audit_log` (append-only chain)
  - immutable append-only log rows with chain hash verification utilities

## Accounting context layer (facts once; interpret many)

- `organization`
  - `id` (UUID PK)
  - identity metadata

- `methodology_version`
  - `id` (UUID PK)
  - `methodology_name`, `methodology_version`
  - integrity metadata (hashes/versioning)

- `reporting_context`
  - `id` (UUID PK)
  - `project_id` → `project.id`
  - `reporting_entity_id` → `organization.id`
  - `methodology_version_id` → `methodology_version.id`
  - consolidation/boundary rules + validity window

- `organization_relationship`
  - time-bounded ownership/control relationships used for consolidation boundaries

- `report_view` (append-only, reproducible snapshot)
  - `id` (UUID PK)
  - references `reporting_context`
  - stores calculation inputs/outputs and a deterministic hash to prove reproducibility

## Notes on immutability

Immutability is enforced at the database layer using PostgreSQL triggers for audit-critical tables (e.g., acknowledgement records and active emission factors). Application logic assumes the DB is authoritative.

## Non-canonical code

Other backends and prototypes are archived under `archive_old/` and are not part of the canonical schema.
