"""Add anomaly explanation fields.

Revision ID: 20251227_02
Revises: 20251227_01_supplier_scope_and_token_evidence
Create Date: 2025-12-27

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251227_02"
down_revision = "20251227_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "anomaly_alert",
        sa.Column("rule_id", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "anomaly_alert",
        sa.Column("explanation", sa.Text(), nullable=True),
    )
    op.add_column(
        "anomaly_alert",
        sa.Column(
            "requires_action",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_index("ix_anomaly_alert_rule_id", "anomaly_alert", ["rule_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_anomaly_alert_rule_id", table_name="anomaly_alert")
    op.drop_column("anomaly_alert", "requires_action")
    op.drop_column("anomaly_alert", "explanation")
    op.drop_column("anomaly_alert", "rule_id")
