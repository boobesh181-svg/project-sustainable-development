"""Add pilot flags to project and MRV reports.

Adds:
- project.pilot (bool)
- mrv_report.pilot (bool)

These flags support LOI / pilot deployments by clearly tagging pilot data so
exports and UI can watermark/label it as non-claim.

Revision ID: 20260101_01
Revises: 20251227_03
Create Date: 2026-01-01

"""

from alembic import op
import sqlalchemy as sa


revision = "20260101_01"
down_revision = "20251227_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project",
        sa.Column(
            "pilot",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "mrv_report",
        sa.Column(
            "pilot",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("mrv_report", "pilot")
    op.drop_column("project", "pilot")
