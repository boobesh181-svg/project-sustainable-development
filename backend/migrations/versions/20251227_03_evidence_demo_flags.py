"""Add demo-only flags to evidence.

Adds:
- evidence.demo_only (bool)
- evidence.non_compliant (bool)

These flags support safe LOI pilots: demo uploads are explicitly marked
and never treated as compliance-grade artifacts.

Revision ID: 20251227_03
Revises: 20251227_02
Create Date: 2025-12-27

"""

from alembic import op
import sqlalchemy as sa


revision = "20251227_03"
down_revision = "20251227_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evidence",
        sa.Column(
            "demo_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "evidence",
        sa.Column(
            "non_compliant",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("evidence", "non_compliant")
    op.drop_column("evidence", "demo_only")
