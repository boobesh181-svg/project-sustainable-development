"""Fix MRV verifier/approver check constraint null handling.

The initial separation-of-duties CHECK used:
  verified_by IS DISTINCT FROM approved_by

In PostgreSQL, NULL IS DISTINCT FROM NULL is FALSE, so DRAFT/SUBMITTED rows
(where both are NULL) violated the constraint.

This migration makes it null-safe:
  verified_by IS NULL OR approved_by IS NULL OR verified_by IS DISTINCT FROM approved_by
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251224_02"
down_revision = "20251224_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE mrv_report
            DROP CONSTRAINT IF EXISTS ck_mrv_verifier_ne_approver;
        """
    )
    op.execute(
        """
        ALTER TABLE mrv_report
            ADD CONSTRAINT ck_mrv_verifier_ne_approver
            CHECK (
                verified_by IS NULL
                OR approved_by IS NULL
                OR verified_by IS DISTINCT FROM approved_by
            );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE mrv_report
            DROP CONSTRAINT IF EXISTS ck_mrv_verifier_ne_approver;
        """
    )
    op.execute(
        """
        ALTER TABLE mrv_report
            ADD CONSTRAINT ck_mrv_verifier_ne_approver
            CHECK (verified_by IS DISTINCT FROM approved_by);
        """
    )
