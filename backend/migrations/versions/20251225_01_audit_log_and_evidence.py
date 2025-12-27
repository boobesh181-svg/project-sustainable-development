"""Audit log append-only enforcement and evidence table.

Adds:
- DB trigger preventing UPDATE/DELETE on audit_log (append-only).
- Request metadata columns on audit_log (ip/user-agent/request-id + optional user FK).
- New evidence table with SHA-256 and DB-level immutability after verification.

Revision ID: 20251225_01
Revises: 20251224_04
Create Date: 2025-12-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20251225_01"
down_revision = "20251224_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- audit_log additions ----
    op.add_column(
        "audit_log",
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "audit_log",
        sa.Column("ip_address", sa.String(length=45), nullable=True),
    )
    op.add_column(
        "audit_log",
        sa.Column("user_agent", sa.Text(), nullable=True),
    )
    op.add_column(
        "audit_log",
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_audit_log_actor_user_id",
        "audit_log",
        ["actor_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_audit_log_actor_user",
        "audit_log",
        "user",
        ["actor_user_id"],
        ["id"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_log_block_update_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Audit log is append-only (no UPDATE/DELETE allowed)';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_audit_log_block_update_delete ON audit_log;
        CREATE TRIGGER trg_audit_log_block_update_delete
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION audit_log_block_update_delete();
        """
    )

    # ---- evidence table ----
    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("upload_type", sa.String(length=32), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        sa.CheckConstraint("LENGTH(sha256) = 64", name="ck_evidence_sha256_len"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_evidence_size_nonneg"),
        sa.CheckConstraint(
            "verified_at IS NULL OR verified_by IS NOT NULL",
            name="ck_evidence_verified_requires_actor",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"], name="fk_evidence_created_by_user"),
        sa.ForeignKeyConstraint(["verified_by"], ["user.id"], name="fk_evidence_verified_by_user"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_sha256", "evidence", ["sha256"], unique=False)
    op.create_index("ix_evidence_created_at", "evidence", ["created_at"], unique=False)
    op.create_index("ix_evidence_created_by", "evidence", ["created_by"], unique=False)

    # Evidence immutability rules:
    # - Never DELETE (append-only)
    # - After verification, block any UPDATE
    # - Before verification, only allow updates to verification fields
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
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_evidence_block_illegal_updates ON evidence;
        CREATE TRIGGER trg_evidence_block_illegal_updates
        BEFORE UPDATE OR DELETE ON evidence
        FOR EACH ROW
        EXECUTE FUNCTION evidence_block_illegal_updates();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_evidence_block_illegal_updates ON evidence;")
    op.execute("DROP FUNCTION IF EXISTS evidence_block_illegal_updates();")
    op.drop_index("ix_evidence_created_by", table_name="evidence")
    op.drop_index("ix_evidence_created_at", table_name="evidence")
    op.drop_index("ix_evidence_sha256", table_name="evidence")
    op.drop_table("evidence")

    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_block_update_delete ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS audit_log_block_update_delete();")

    op.drop_constraint("fk_audit_log_actor_user", "audit_log", type_="foreignkey")
    op.drop_index("ix_audit_log_actor_user_id", table_name="audit_log")
    op.drop_column("audit_log", "request_id")
    op.drop_column("audit_log", "user_agent")
    op.drop_column("audit_log", "ip_address")
    op.drop_column("audit_log", "actor_user_id")
