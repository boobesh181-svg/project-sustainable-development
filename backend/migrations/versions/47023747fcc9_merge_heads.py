"""merge heads

Revision ID: 47023747fcc9
Revises: 002_add_scope3_boundaries, add_carbon_models
Create Date: 2025-12-15 21:36:58.261912

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47023747fcc9'
down_revision: Union[str, Sequence[str], None] = ('002_add_scope3_boundaries', 'add_carbon_models')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
