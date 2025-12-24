"""Add project boundary baseline locks.

Adds explicit reporting period and baseline lock metadata to Project.
Once baseline is locked, relevant boundary fields become immutable at DB level.

Revision ID: 20251224_04
Revises: 20251224_03
Create Date: 2025-12-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20251224_04"
down_revision = "20251224_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project",
        sa.Column("reporting_period_start", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "project",
        sa.Column("reporting_period_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "project",
        sa.Column("baseline_locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "project",
        sa.Column("baseline_locked_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_project_baseline_locked_by_user",
        "project",
        "user",
        ["baseline_locked_by"],
        ["id"],
    )

    op.execute(
        """
        ALTER TABLE project
            ADD CONSTRAINT ck_project_baseline_lock_requires_actor
            CHECK (baseline_locked_at IS NULL OR baseline_locked_by IS NOT NULL);
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION project_block_boundary_edits_after_lock() RETURNS trigger AS $$
        BEGIN
            IF (OLD.baseline_locked_at IS NOT NULL) THEN
                IF NEW.reporting_period_start IS DISTINCT FROM OLD.reporting_period_start
                   OR NEW.reporting_period_end IS DISTINCT FROM OLD.reporting_period_end
                   OR NEW.baseline_locked_at IS DISTINCT FROM OLD.baseline_locked_at
                   OR NEW.baseline_locked_by IS DISTINCT FROM OLD.baseline_locked_by
                THEN
                    RAISE EXCEPTION 'Project baseline/reporting period is locked and immutable';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_project_block_boundary_edits_after_lock ON project;
        CREATE TRIGGER trg_project_block_boundary_edits_after_lock
        BEFORE UPDATE ON project
        FOR EACH ROW
        EXECUTE FUNCTION project_block_boundary_edits_after_lock();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_project_block_boundary_edits_after_lock ON project;")
    op.execute("DROP FUNCTION IF EXISTS project_block_boundary_edits_after_lock();")
    op.execute(
        "ALTER TABLE project DROP CONSTRAINT IF EXISTS ck_project_baseline_lock_requires_actor;"
    )

    op.drop_constraint(
        "fk_project_baseline_locked_by_user",
        "project",
        type_="foreignkey",
    )
    op.drop_column("project", "baseline_locked_by")
    op.drop_column("project", "baseline_locked_at")
    op.drop_column("project", "reporting_period_end")
    op.drop_column("project", "reporting_period_start")
