"""Add MRV QA columns for flags and certificate hash

Revision ID: add_mrv_qa_columns
Revises: add_mrv_tables
Create Date: 2025-12-12 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_mrv_qa_columns'
down_revision = 'add_mrv_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add QA columns to MRV tables"""
    
    # Add mrv_flags column to mrv_sample table
    op.add_column('mrv_sample', sa.Column('mrv_flags', sa.JSON(), server_default='{}'))
    
    # Add certificate_hash column to mrv_test table
    op.add_column('mrv_test', sa.Column('certificate_hash', sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Remove QA columns from MRV tables"""
    
    # Remove mrv_flags column from mrv_sample table
    op.drop_column('mrv_sample', 'mrv_flags')
    
    # Remove certificate_hash column from mrv_test table
    op.drop_column('mrv_test', 'certificate_hash')
