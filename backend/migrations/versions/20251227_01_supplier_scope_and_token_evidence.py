"""Supplier scope on users and link evidence to material tokens.

Adds:
- user.supplier_id (nullable FK -> supplier.id) for supplier-scoped visibility.
- evidence.material_token_id (nullable FK -> material_token.id) to attach EPD/invoice evidence to deliveries.
- evidence.decision (nullable) for verifier decision tags.

Also updates the evidence immutability trigger to treat report_id/material_token_id as immutable core fields.

Revision ID: 20251227_01
Revises: 20251225_02
Create Date: 2025-12-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20251227_01"
down_revision = "20251225_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- user.supplier_id ----
    op.add_column(
        "user",
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_user_supplier_id", "user", ["supplier_id"], unique=False)
    op.create_foreign_key(
        "fk_user_supplier",
        "user",
        "supplier",
        ["supplier_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ---- evidence.material_token_id + evidence.decision ----
    op.add_column(
        "evidence",
        sa.Column("material_token_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_evidence_material_token_id",
        "evidence",
        ["material_token_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_evidence_material_token",
        "evidence",
        "material_token",
        ["material_token_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "evidence",
        sa.Column("decision", sa.String(length=32), nullable=True),
    )
    op.create_check_constraint(
        "ck_evidence_decision_allowed",
        "evidence",
        "decision IS NULL OR decision IN ('accepted','rejected','needs_correction')",
    )

    # Update immutability trigger to include newly-linkable FKs as immutable core fields.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION evidence_block_illegal_updates() RETURNS trigger AS $$
        BEGIN
            IF (TG_OP = 'DELETE') THEN
                RAISE EXCEPTION 'Evidence rows are append-only and cannot be deleted';
            END IF;

            IF (OLD.verified_at IS NOT NULL) THEN
                RAISE EXCEPTION 'Evidence is verified and immutable';
            END IF;

            IF NEW.upload_type IS DISTINCT FROM OLD.upload_type
               OR NEW.storage_path IS DISTINCT FROM OLD.storage_path
               OR NEW.sha256 IS DISTINCT FROM OLD.sha256
               OR NEW.size_bytes IS DISTINCT FROM OLD.size_bytes
               OR NEW.content_type IS DISTINCT FROM OLD.content_type
               OR NEW.original_filename IS DISTINCT FROM OLD.original_filename
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR NEW.created_by IS DISTINCT FROM OLD.created_by
               OR NEW.report_id IS DISTINCT FROM OLD.report_id
               OR NEW.material_token_id IS DISTINCT FROM OLD.material_token_id
            THEN
                RAISE EXCEPTION 'Evidence core fields are immutable';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    # Revert trigger core-field list (drop back to the previous definition).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION evidence_block_illegal_updates() RETURNS trigger AS $$
        BEGIN
            IF (TG_OP = 'DELETE') THEN
                RAISE EXCEPTION 'Evidence rows are append-only and cannot be deleted';
            END IF;

            IF (OLD.verified_at IS NOT NULL) THEN
                RAISE EXCEPTION 'Evidence is verified and immutable';
            END IF;

            IF NEW.upload_type IS DISTINCT FROM OLD.upload_type
               OR NEW.storage_path IS DISTINCT FROM OLD.storage_path
               OR NEW.sha256 IS DISTINCT FROM OLD.sha256
               OR NEW.size_bytes IS DISTINCT FROM OLD.size_bytes
               OR NEW.content_type IS DISTINCT FROM OLD.content_type
               OR NEW.original_filename IS DISTINCT FROM OLD.original_filename
               OR NEW.created_at IS DISTINCT FROM OLD.created_at
               OR NEW.created_by IS DISTINCT FROM OLD.created_by
            THEN
                RAISE EXCEPTION 'Evidence core fields are immutable';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.drop_constraint("ck_evidence_decision_allowed", "evidence", type_="check")
    op.drop_column("evidence", "decision")

    op.drop_constraint("fk_evidence_material_token", "evidence", type_="foreignkey")
    op.drop_index("ix_evidence_material_token_id", table_name="evidence")
    op.drop_column("evidence", "material_token_id")

    op.drop_constraint("fk_user_supplier", "user", type_="foreignkey")
    op.drop_index("ix_user_supplier_id", table_name="user")
    op.drop_column("user", "supplier_id")
