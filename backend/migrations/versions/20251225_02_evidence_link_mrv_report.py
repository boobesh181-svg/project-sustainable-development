"""Link evidence to MRV reports.

Adds:
- evidence.report_id (nullable FK -> mrv_report.id)

Keeps existing evidence immutability trigger behavior.

Revision ID: 20251225_02
Revises: 20251225_01
Create Date: 2025-12-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20251225_02"
down_revision = "20251225_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evidence",
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_evidence_report_id", "evidence", ["report_id"], unique=False)
    op.create_foreign_key(
        "fk_evidence_report",
        "evidence",
        "mrv_report",
        ["report_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_evidence_report", "evidence", type_="foreignkey")
    op.drop_index("ix_evidence_report_id", table_name="evidence")
    op.drop_column("evidence", "report_id")
