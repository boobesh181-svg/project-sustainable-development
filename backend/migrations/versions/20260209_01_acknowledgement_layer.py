"""Notification & acknowledgement layer tables.

Adds append-only, hash-addressed records for contemporaneous multi-party acknowledgement:
- activity_record: canonical activity/event record
- event_notification: notification to a counterparty with deadline
- event_response: append-only responses (ack/comment/dispute/no-response-auto)
- event_status_ledger: append-only derived status ledger computed from responses

All tables are immutable (no UPDATE/DELETE) at DB-level via triggers, consistent with audit/evidence.

Revision ID: 20260209_01
Revises: 20260101_02
Create Date: 2026-02-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260209_01"
down_revision = "20260101_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- activity_record ----
    op.create_table(
        "activity_record",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "activity_type",
            sa.Enum(
                "MATERIAL_TOKEN_REDEEMED",
                "DELIVERY_VERIFICATION_CREATED",
                "MRV_REPORT_CREATED",
                name="activity_type",
            ),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("delivery_verification_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mrv_report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("activity_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "activity_hash ~ '^[0-9a-f]{64}$'",
            name="ck_activity_record_hash_format",
        ),
        sa.CheckConstraint(
            "(material_token_id IS NOT NULL)::int + (delivery_verification_id IS NOT NULL)::int + (mrv_report_id IS NOT NULL)::int = 1",
            name="ck_activity_record_exactly_one_source",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], name="fk_activity_record_project"),
        sa.ForeignKeyConstraint(
            ["material_token_id"],
            ["material_token.id"],
            name="fk_activity_record_material_token",
        ),
        sa.ForeignKeyConstraint(
            ["delivery_verification_id"],
            ["delivery_verification.id"],
            name="fk_activity_record_delivery_verification",
        ),
        sa.ForeignKeyConstraint(
            ["mrv_report_id"],
            ["mrv_report.id"],
            name="fk_activity_record_mrv_report",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["user.id"],
            name="fk_activity_record_created_by_user",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("activity_hash", name="uq_activity_record_activity_hash"),
    )
    op.create_index("ix_activity_record_project_id", "activity_record", ["project_id"], unique=False)
    op.create_index(
        "ix_activity_record_project_type_time",
        "activity_record",
        ["project_id", "activity_type", "occurred_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION activity_record_block_update_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Activity records are append-only (no UPDATE/DELETE allowed)';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_activity_record_block_update_delete ON activity_record;
        CREATE TRIGGER trg_activity_record_block_update_delete
        BEFORE UPDATE OR DELETE ON activity_record
        FOR EACH ROW
        EXECUTE FUNCTION activity_record_block_update_delete();
        """
    )

    # ---- event_notification ----
    op.create_table(
        "event_notification",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notified_party_org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notified_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response_deadline_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notification_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "delivery_channel",
            sa.Enum("in_app", "email", "webhook", name="delivery_channel"),
            nullable=False,
        ),
        sa.Column("demo_watermark", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "notification_hash ~ '^[0-9a-f]{64}$'",
            name="ck_event_notification_hash_format",
        ),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activity_record.id"],
            name="fk_event_notification_activity",
        ),
        sa.ForeignKeyConstraint(
            ["notified_user_id"],
            ["user.id"],
            name="fk_event_notification_notified_user",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notification_hash", name="uq_event_notification_notification_hash"),
    )
    op.create_index(
        "ix_event_notification_activity_id", "event_notification", ["activity_id"], unique=False
    )
    op.create_index(
        "ix_event_notification_notified_user_id",
        "event_notification",
        ["notified_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_event_notification_response_deadline_timestamp",
        "event_notification",
        ["response_deadline_timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_event_notification_user_deadline",
        "event_notification",
        ["notified_user_id", "response_deadline_timestamp"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION event_notification_block_update_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Event notifications are append-only (no UPDATE/DELETE allowed)';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_event_notification_block_update_delete ON event_notification;
        CREATE TRIGGER trg_event_notification_block_update_delete
        BEFORE UPDATE OR DELETE ON event_notification
        FOR EACH ROW
        EXECUTE FUNCTION event_notification_block_update_delete();
        """
    )

    # ---- event_response ----
    op.create_table(
        "event_response",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("responder_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "response_type",
            sa.Enum(
                "ACKNOWLEDGED",
                "COMMENTED",
                "DISPUTED",
                "NO_RESPONSE_AUTO",
                name="event_response_type",
            ),
            nullable=False,
        ),
        sa.Column("response_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response_comment", sa.Text(), nullable=True),
        sa.Column("response_hash", sa.String(length=64), nullable=False),
        sa.Column("demo_watermark", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "response_hash ~ '^[0-9a-f]{64}$'",
            name="ck_event_response_hash_format",
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["event_notification.id"],
            name="fk_event_response_notification",
        ),
        sa.ForeignKeyConstraint(
            ["responder_user_id"],
            ["user.id"],
            name="fk_event_response_responder_user",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("response_hash", name="uq_event_response_response_hash"),
    )
    op.create_index("ix_event_response_notification_id", "event_response", ["notification_id"], unique=False)
    op.create_index("ix_event_response_responder_user_id", "event_response", ["responder_user_id"], unique=False)
    op.create_index(
        "ix_event_response_notification_time",
        "event_response",
        ["notification_id", "response_timestamp"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION event_response_block_update_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Event responses are append-only (no UPDATE/DELETE allowed)';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_event_response_block_update_delete ON event_response;
        CREATE TRIGGER trg_event_response_block_update_delete
        BEFORE UPDATE OR DELETE ON event_response
        FOR EACH ROW
        EXECUTE FUNCTION event_response_block_update_delete();
        """
    )

    # ---- event_status_ledger ----
    op.create_table(
        "event_status_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "derived_status",
            sa.Enum(
                "UNSEEN",
                "SEEN",
                "ACKNOWLEDGED",
                "DISPUTED",
                "DEEMED_OBSERVED",
                name="event_derived_status",
            ),
            nullable=False,
        ),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("computation_basis_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "computation_basis_hash ~ '^[0-9a-f]{64}$'",
            name="ck_event_status_ledger_basis_hash_format",
        ),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activity_record.id"],
            name="fk_event_status_ledger_activity",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "computation_basis_hash",
            name="uq_event_status_ledger_computation_basis_hash",
        ),
    )
    op.create_index(
        "ix_event_status_ledger_activity_id", "event_status_ledger", ["activity_id"], unique=False
    )
    op.create_index(
        "ix_event_status_ledger_activity_time",
        "event_status_ledger",
        ["activity_id", "computed_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION event_status_ledger_block_update_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Event status ledger is append-only (no UPDATE/DELETE allowed)';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_event_status_ledger_block_update_delete ON event_status_ledger;
        CREATE TRIGGER trg_event_status_ledger_block_update_delete
        BEFORE UPDATE OR DELETE ON event_status_ledger
        FOR EACH ROW
        EXECUTE FUNCTION event_status_ledger_block_update_delete();
        """
    )


def downgrade() -> None:
    # Drop triggers/functions first
    op.execute("DROP TRIGGER IF EXISTS trg_event_status_ledger_block_update_delete ON event_status_ledger;")
    op.execute("DROP FUNCTION IF EXISTS event_status_ledger_block_update_delete();")

    op.execute("DROP TRIGGER IF EXISTS trg_event_response_block_update_delete ON event_response;")
    op.execute("DROP FUNCTION IF EXISTS event_response_block_update_delete();")

    op.execute("DROP TRIGGER IF EXISTS trg_event_notification_block_update_delete ON event_notification;")
    op.execute("DROP FUNCTION IF EXISTS event_notification_block_update_delete();")

    op.execute("DROP TRIGGER IF EXISTS trg_activity_record_block_update_delete ON activity_record;")
    op.execute("DROP FUNCTION IF EXISTS activity_record_block_update_delete();")

    # Drop tables
    op.drop_index("ix_event_status_ledger_activity_time", table_name="event_status_ledger")
    op.drop_index("ix_event_status_ledger_activity_id", table_name="event_status_ledger")
    op.drop_table("event_status_ledger")

    op.drop_index("ix_event_response_notification_time", table_name="event_response")
    op.drop_index("ix_event_response_responder_user_id", table_name="event_response")
    op.drop_index("ix_event_response_notification_id", table_name="event_response")
    op.drop_table("event_response")

    op.drop_index("ix_event_notification_user_deadline", table_name="event_notification")
    op.drop_index("ix_event_notification_response_deadline_timestamp", table_name="event_notification")
    op.drop_index("ix_event_notification_notified_user_id", table_name="event_notification")
    op.drop_index("ix_event_notification_activity_id", table_name="event_notification")
    op.drop_table("event_notification")

    op.drop_index("ix_activity_record_project_type_time", table_name="activity_record")
    op.drop_index("ix_activity_record_project_id", table_name="activity_record")
    op.drop_table("activity_record")

    # Drop enum types (Postgres only)
    op.execute("DROP TYPE IF EXISTS event_derived_status;")
    op.execute("DROP TYPE IF EXISTS event_response_type;")
    op.execute("DROP TYPE IF EXISTS delivery_channel;")
    op.execute("DROP TYPE IF EXISTS activity_type;")
