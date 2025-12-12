"""
Add carbon accounting models

Revision ID: add_carbon_models
Revises: add_mrv_qa_columns
Create Date: 2025-12-12 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_carbon_models'
down_revision: Union[str, None] = 'add_mrv_qa_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add CO2 contribution fields to MRVTest
    op.add_column('mrv_test', sa.Column('co2_contribution_kg', sa.Float(), nullable=True))
    op.add_column('mrv_test', sa.Column('lca_method', sa.String(length=100), nullable=True))
    
    # Create CarbonLedger table
    op.create_table('carbon_ledger',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('sample_id', sa.String(length=50), nullable=False),
        sa.Column('test_id', sa.String(length=36), nullable=True),
        sa.Column('co2_kg', sa.Float(), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('material_type', sa.String(length=100), nullable=False),
        sa.Column('quantity_tonnes', sa.Float(), nullable=True),
        sa.Column('lca_method', sa.String(length=100), nullable=True),
        sa.Column('calculation_details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(datetime(\'now\'))'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ),
        sa.ForeignKeyConstraint(['sample_id'], ['mrv_sample.sample_id'], ),
        sa.ForeignKeyConstraint(['test_id'], ['mrv_test.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('idx_carbon_ledger_project_id'), 'carbon_ledger', ['project_id'], unique=False)
    op.create_index(op.f('idx_carbon_ledger_sample_id'), 'carbon_ledger', ['sample_id'], unique=False)
    op.create_index(op.f('idx_carbon_ledger_created_at'), 'carbon_ledger', ['created_at'], unique=False)
    
    # Create CarbonCreditIssuance table
    op.create_table('carbon_credit_issuance',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('credits_t', sa.Float(), nullable=False),
        sa.Column('value_usd', sa.Float(), nullable=False),
        sa.Column('credit_rate_usd_per_ton', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.text('(datetime(\'now\'))'), nullable=False),
        sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('calculation_details', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('idx_carbon_credit_issuance_project_id'), 'carbon_credit_issuance', ['project_id'], unique=False)
    op.create_index(op.f('idx_carbon_credit_issuance_status'), 'carbon_credit_issuance', ['status'], unique=False)
    op.create_index(op.f('idx_carbon_credit_issuance_issued_at'), 'carbon_credit_issuance', ['issued_at'], unique=False)


def downgrade() -> None:
    # Drop CarbonCreditIssuance table
    op.drop_index(op.f('idx_carbon_credit_issuance_issued_at'), table_name='carbon_credit_issuance')
    op.drop_index(op.f('idx_carbon_credit_issuance_status'), table_name='carbon_credit_issuance')
    op.drop_index(op.f('idx_carbon_credit_issuance_project_id'), table_name='carbon_credit_issuance')
    op.drop_table('carbon_credit_issuance')
    
    # Drop CarbonLedger table
    op.drop_index(op.f('idx_carbon_ledger_created_at'), table_name='carbon_ledger')
    op.drop_index(op.f('idx_carbon_ledger_sample_id'), table_name='carbon_ledger')
    op.drop_index(op.f('idx_carbon_ledger_project_id'), table_name='carbon_ledger')
    op.drop_table('carbon_ledger')
    
    # Remove CO2 contribution fields from MRVTest
    op.drop_column('mrv_test', 'lca_method')
    op.drop_column('mrv_test', 'co2_contribution_kg')
