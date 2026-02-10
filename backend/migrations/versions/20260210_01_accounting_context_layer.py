"""Accounting context layer.

Adds the accounting-context interpretation layer without modifying immutable event tables.

Tables:
- organization
- methodology_version (binds to emission_factor.methodology_reference)
- reporting_context
- organization_relationships
- report_view (append-only generated views)

Immutability/append-only:
- All tables in this layer are protected with BEFORE UPDATE/DELETE triggers.

Revision ID: 20260210_01
Revises: 20260209_01
Create Date: 2026-02-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260210_01"
down_revision = "20260209_01"
branch_labels = None
depends_on = None


def _block_update_delete(table: str, fn: str, trg: str, message: str) -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {fn}() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '{message}';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        DROP TRIGGER IF EXISTS {trg} ON {table};
        CREATE TRIGGER {trg}
        BEFORE UPDATE OR DELETE ON {table}
        FOR EACH ROW
        EXECUTE FUNCTION {fn}();
        """
    )


def upgrade() -> None:
    op.create_table(
        "organization",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_organization_name"),
    )

    _block_update_delete(
        "organization",
        "organization_block_update_delete",
        "trg_organization_block_update_delete",
        "Organizations are append-only (no UPDATE/DELETE allowed)",
    )

    op.create_table(
        "methodology_version",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_methodology_version_code"),
    )

    _block_update_delete(
        "methodology_version",
        "methodology_version_block_update_delete",
        "trg_methodology_version_block_update_delete",
        "Methodology versions are append-only (no UPDATE/DELETE allowed)",
    )

    op.create_table(
        "reporting_context",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporting_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "consolidation_method",
            sa.Enum(
                "EQUITY",
                "FINANCIAL_CONTROL",
                "OPERATIONAL_CONTROL",
                name="consolidation_method",
            ),
            nullable=False,
        ),
        sa.Column(
            "reporting_purpose",
            sa.Enum("ESG", "PROCUREMENT", "TAX", "DISCLOSURE", name="reporting_purpose"),
            nullable=False,
        ),
        sa.Column("methodology_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_reporting_context_valid_window",
        ),
        sa.ForeignKeyConstraint(
            ["reporting_entity_id"],
            ["organization.id"],
            name="fk_reporting_context_reporting_entity",
        ),
        sa.ForeignKeyConstraint(
            ["methodology_version_id"],
            ["methodology_version.id"],
            name="fk_reporting_context_methodology_version",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reporting_context_entity_method_window",
        "reporting_context",
        ["reporting_entity_id", "methodology_version_id", "valid_from"],
        unique=False,
    )
    op.create_index(
        "ix_reporting_context_reporting_entity_id",
        "reporting_context",
        ["reporting_entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_reporting_context_methodology_version_id",
        "reporting_context",
        ["methodology_version_id"],
        unique=False,
    )

    _block_update_delete(
        "reporting_context",
        "reporting_context_block_update_delete",
        "trg_reporting_context_block_update_delete",
        "Reporting contexts are append-only (no UPDATE/DELETE allowed)",
    )

    op.create_table(
        "organization_relationship",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role_type",
            sa.Enum(
                "DEVELOPER",
                "CONTRACTOR",
                "SUPPLIER",
                "OPERATOR",
                name="organization_role_type",
            ),
            nullable=False,
        ),
        sa.Column("ownership_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("financial_control", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("operational_control", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ownership_percentage IS NULL OR (ownership_percentage >= 0 AND ownership_percentage <= 100)",
            name="ck_org_rel_ownership_pct_range",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_org_rel_valid_window",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], name="fk_org_rel_project"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name="fk_org_rel_organization",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_rel_project_org_window",
        "organization_relationship",
        ["project_id", "organization_id", "valid_from"],
        unique=False,
    )
    op.create_index(
        "ix_organization_relationship_project_id",
        "organization_relationship",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_relationship_organization_id",
        "organization_relationship",
        ["organization_id"],
        unique=False,
    )

    _block_update_delete(
        "organization_relationship",
        "organization_relationship_block_update_delete",
        "trg_organization_relationship_block_update_delete",
        "Organization relationships are append-only (no UPDATE/DELETE allowed)",
    )

    op.create_table(
        "report_view",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporting_context_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_emissions", sa.Numeric(18, 6), nullable=False),
        sa.Column("calculation_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "calculation_hash ~ '^[0-9a-f]{64}$'",
            name="ck_report_view_calc_hash_format",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], name="fk_report_view_project"),
        sa.ForeignKeyConstraint(
            ["reporting_context_id"],
            ["reporting_context.id"],
            name="fk_report_view_reporting_context",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_report_view_project_context_time",
        "report_view",
        ["project_id", "reporting_context_id", "generated_at"],
        unique=False,
    )
    op.create_index("ix_report_view_project_id", "report_view", ["project_id"], unique=False)
    op.create_index(
        "ix_report_view_reporting_context_id",
        "report_view",
        ["reporting_context_id"],
        unique=False,
    )

    _block_update_delete(
        "report_view",
        "report_view_block_update_delete",
        "trg_report_view_block_update_delete",
        "Report views are append-only (no UPDATE/DELETE allowed)",
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_report_view_block_update_delete ON report_view;")
    op.execute("DROP FUNCTION IF EXISTS report_view_block_update_delete();")

    op.execute("DROP TRIGGER IF EXISTS trg_organization_relationship_block_update_delete ON organization_relationship;")
    op.execute("DROP FUNCTION IF EXISTS organization_relationship_block_update_delete();")

    op.execute("DROP TRIGGER IF EXISTS trg_reporting_context_block_update_delete ON reporting_context;")
    op.execute("DROP FUNCTION IF EXISTS reporting_context_block_update_delete();")

    op.execute("DROP TRIGGER IF EXISTS trg_methodology_version_block_update_delete ON methodology_version;")
    op.execute("DROP FUNCTION IF EXISTS methodology_version_block_update_delete();")

    op.execute("DROP TRIGGER IF EXISTS trg_organization_block_update_delete ON organization;")
    op.execute("DROP FUNCTION IF EXISTS organization_block_update_delete();")

    op.drop_index("ix_report_view_reporting_context_id", table_name="report_view")
    op.drop_index("ix_report_view_project_id", table_name="report_view")
    op.drop_index("ix_report_view_project_context_time", table_name="report_view")
    op.drop_table("report_view")

    op.drop_index("ix_organization_relationship_organization_id", table_name="organization_relationship")
    op.drop_index("ix_organization_relationship_project_id", table_name="organization_relationship")
    op.drop_index("ix_org_rel_project_org_window", table_name="organization_relationship")
    op.drop_table("organization_relationship")

    op.drop_index("ix_reporting_context_methodology_version_id", table_name="reporting_context")
    op.drop_index("ix_reporting_context_reporting_entity_id", table_name="reporting_context")
    op.drop_index("ix_reporting_context_entity_method_window", table_name="reporting_context")
    op.drop_table("reporting_context")

    op.drop_table("methodology_version")
    op.drop_table("organization")

    op.execute("DROP TYPE IF EXISTS organization_role_type;")
    op.execute("DROP TYPE IF EXISTS reporting_purpose;")
    op.execute("DROP TYPE IF EXISTS consolidation_method;")
