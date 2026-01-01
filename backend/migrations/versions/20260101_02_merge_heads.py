"""Merge Alembic heads.

This repository historically accumulated multiple Alembic heads.
This merge revision unifies the migration graph so `alembic upgrade head`
works and runtime startup checks can validate a single converged head.

Revision ID: 20260101_02
Revises: 20260101_01, 980a43d09d87
Create Date: 2026-01-01

"""

from alembic import op


revision = "20260101_02"
down_revision = ("20260101_01", "980a43d09d87")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge revision: no schema changes.
    pass


def downgrade() -> None:
    # Downgrade is not supported for merge-only revision.
    pass
