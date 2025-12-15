"""Add Scope 3 boundary models

Revision ID: 002_add_scope3_boundaries
Revises: 001_add_scope3_materials
Create Date: 2025-12-15 21:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_add_scope3_boundaries'
down_revision = '001_add_scope3_materials'
branch_labels = None
depends_on = None


def upgrade():
    # Create organizational_boundaries table
    op.create_table('organizational_boundaries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('boundary_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('inclusion_basis', sa.Enum('financial_control', 'operational_control', 'equity_share', name='inclusionbasis'), nullable=False),
        sa.Column('consolidation_approach', sa.String(length=50), nullable=False),
        sa.Column('country_code', sa.String(length=2), nullable=False),
        sa.Column('geographic_scope', sa.String(length=500), nullable=True),
        sa.Column('reporting_period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reporting_period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('legal_entity_identifiers', sa.Text(), nullable=True),
        sa.Column('operational_segments', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('approval_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'boundary_name', name='uq_org_boundary_name')
    )
    op.create_index('ix_org_boundary_period', 'organizational_boundaries', ['reporting_period_start', 'reporting_period_end'], unique=False)

    # Create operational_boundaries table
    op.create_table('operational_boundaries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organizational_boundary_id', sa.UUID(), nullable=False),
        sa.Column('boundary_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('scope1_included', sa.Boolean(), nullable=False),
        sa.Column('scope2_included', sa.Boolean(), nullable=False),
        sa.Column('scope3_categories_included', sa.Text(), nullable=True),
        sa.Column('construction_projects_included', sa.Boolean(), nullable=False),
        sa.Column('construction_material_categories', sa.Text(), nullable=True),
        sa.Column('excluded_categories', sa.Text(), nullable=True),
        sa.Column('exclusion_justifications', sa.Text(), nullable=True),
        sa.Column('methodology_version', sa.String(length=20), nullable=False),
        sa.Column('calculation_methodology', sa.String(length=100), nullable=False),
        sa.Column('reporting_framework', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('approval_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['organizational_boundary_id'], ['organizational_boundaries.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organizational_boundary_id', 'boundary_name', name='uq_op_boundary_name')
    )

    # Create project_boundaries table
    op.create_table('project_boundaries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('operational_boundary_id', sa.UUID(), nullable=False),
        sa.Column('boundary_snapshot', sa.Text(), nullable=False),
        sa.Column('included_material_categories', sa.Text(), nullable=False),
        sa.Column('excluded_material_categories', sa.Text(), nullable=True),
        sa.Column('project_specific_inclusions', sa.Text(), nullable=True),
        sa.Column('project_specific_exclusions', sa.Text(), nullable=True),
        sa.Column('adjustment_justifications', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'submitted', 'under_review', 'approved', 'locked', 'rejected', name='projectboundarystatus'), nullable=False),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('locked_by', sa.UUID(), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_by', sa.UUID(), nullable=True),
        sa.Column('methodology_version', sa.String(length=20), nullable=False),
        sa.Column('emission_factor_version', sa.String(length=20), nullable=False),
        sa.Column('calculation_rules', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['locked_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['operational_boundary_id'], ['operational_boundaries.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id')
    )
    op.create_index('ix_project_boundary_status', 'project_boundaries', ['status', 'locked_at'], unique=False)

    # Create boundary_change_requests table
    op.create_table('boundary_change_requests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('project_boundary_id', sa.UUID(), nullable=False),
        sa.Column('requested_by', sa.UUID(), nullable=False),
        sa.Column('change_type', sa.String(length=50), nullable=False),
        sa.Column('change_description', sa.Text(), nullable=False),
        sa.Column('current_configuration', sa.Text(), nullable=False),
        sa.Column('proposed_configuration', sa.Text(), nullable=False),
        sa.Column('change_justification', sa.Text(), nullable=False),
        sa.Column('impact_assessment', sa.Text(), nullable=True),
        sa.Column('material_impact', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reviewed_by', sa.UUID(), nullable=True),
        sa.Column('review_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.Column('implemented_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('implemented_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['implemented_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['project_boundary_id'], ['project_boundaries.id'], ),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create boundary_audit_logs table
    op.create_table('boundary_audit_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('project_boundary_id', sa.UUID(), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('actor_id', sa.UUID(), nullable=False),
        sa.Column('action_description', sa.Text(), nullable=False),
        sa.Column('previous_state', sa.Text(), nullable=True),
        sa.Column('new_state', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['project_boundary_id'], ['project_boundaries.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_boundary_audit_project', 'boundary_audit_logs', ['project_boundary_id', 'created_at'], unique=False)
    op.create_index('ix_boundary_audit_actor', 'boundary_audit_logs', ['actor_id', 'created_at'], unique=False)


def downgrade():
    op.drop_table('boundary_audit_logs')
    op.drop_table('boundary_change_requests')
    op.drop_table('project_boundaries')
    op.drop_table('operational_boundaries')
    op.drop_table('organizational_boundaries')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS inclusionbasis')
    op.execute('DROP TYPE IF EXISTS projectboundarystatus')
