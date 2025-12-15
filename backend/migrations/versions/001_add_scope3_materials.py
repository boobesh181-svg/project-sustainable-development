"""Add Scope 3 material models

Revision ID: 001_add_scope3_materials
Revises: 
Create Date: 2025-12-15 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_add_scope3_materials'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create material_categories table
    op.create_table('material_categories',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.Enum('cement', 'concrete', 'steel', 'aluminum', 'timber', 'glass', 'plastics', 'insulation', 'masonry', 'roofing', 'paints_coatings', 'adhesives_sealants', 'electrical', 'plumbing', 'hvac', 'finishes', name='materialcategory'), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('standardized_unit', sa.Enum('kg', 'tonne', 'm3', 'm2', 'm', 'L', 'piece', 'kWh', name='standardunit'), nullable=False),
        sa.Column('requires_batch_tracking', sa.Boolean(), nullable=False),
        sa.Column('co2_calculation_method', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_material_categories_name'), 'material_categories', ['name'], unique=False)

    # Create material_subtypes table
    op.create_table('material_subtypes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('standard_density', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('standard_specification', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['material_categories.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category_id', 'name', name='uq_category_subtype')
    )

    # Create emission_factors table
    op.create_table('emission_factors',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('material_category_id', sa.UUID(), nullable=False),
        sa.Column('material_subtype_id', sa.UUID(), nullable=True),
        sa.Column('factor_type', sa.Enum('primary_verified', 'primary_unverified', 'national_default', 'international_fallback', name='emissionfactortype'), nullable=False),
        sa.Column('co2_factor_kg', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('uncertainty_lower', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('uncertainty_upper', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('data_quality_tier', sa.Enum('tier_1', 'tier_2', 'tier_3', 'tier_4', name='dataqualitytier'), nullable=False),
        sa.Column('source_reference', sa.String(length=200), nullable=False),
        sa.Column('source_document_url', sa.String(length=500), nullable=True),
        sa.Column('validity_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('validity_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=False),
        sa.Column('supplier_id', sa.UUID(), nullable=True),
        sa.Column('verification_status', sa.String(length=20), nullable=False),
        sa.Column('calculation_methodology', sa.String(length=100), nullable=False),
        sa.Column('geographic_scope', sa.String(length=100), nullable=True),
        sa.Column('temporal_scope', sa.String(length=50), nullable=True),
        sa.Column('included_gases', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['material_category_id'], ['material_categories.id'], ),
        sa.ForeignKeyConstraint(['material_subtype_id'], ['material_subtypes.id'], ),
        sa.ForeignKeyConstraint(['supplier_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_emission_factor_lookup', 'emission_factors', ['material_category_id', 'material_subtype_id', 'factor_type', 'validity_start'], unique=False)
    op.create_index('ix_emission_factor_validity', 'emission_factors', ['validity_start', 'validity_end'], unique=False)

    # Create activity_data table
    op.create_table('activity_data',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('material_category_id', sa.UUID(), nullable=False),
        sa.Column('material_subtype_id', sa.UUID(), nullable=True),
        sa.Column('emission_factor_id', sa.UUID(), nullable=False),
        sa.Column('batch_identifier', sa.String(length=100), nullable=False),
        sa.Column('quantity_submitted', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('unit_submitted', sa.String(length=20), nullable=False),
        sa.Column('quantity_normalized', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('unit_normalized', sa.Enum('kg', 'tonne', 'm3', 'm2', 'm', 'L', 'piece', 'kWh', name='standardunit'), nullable=False),
        sa.Column('emission_factor_used', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('co2_calculated', sa.Numeric(precision=15, scale=6), nullable=False),
        sa.Column('uncertainty_lower', sa.Numeric(precision=15, scale=6), nullable=True),
        sa.Column('uncertainty_upper', sa.Numeric(precision=15, scale=6), nullable=True),
        sa.Column('submission_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('supplier_id', sa.UUID(), nullable=False),
        sa.Column('submitted_by', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('verification_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_by', sa.UUID(), nullable=True),
        sa.Column('verification_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['emission_factor_id'], ['emission_factors.id'], ),
        sa.ForeignKeyConstraint(['material_category_id'], ['material_categories.id'], ),
        sa.ForeignKeyConstraint(['material_subtype_id'], ['material_subtypes.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['submitted_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['supplier_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('batch_identifier', 'project_id', name='uq_batch_project')
    )
    op.create_index('ix_activity_data_project', 'activity_data', ['project_id', 'submission_date'], unique=False)
    op.create_index('ix_activity_data_supplier', 'activity_data', ['supplier_id', 'submission_date'], unique=False)

    # Create activity_data_corrections table
    op.create_table('activity_data_corrections',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('original_submission_id', sa.UUID(), nullable=False),
        sa.Column('corrected_submission_id', sa.UUID(), nullable=False),
        sa.Column('correction_reason', sa.Text(), nullable=False),
        sa.Column('correction_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('corrected_by', sa.UUID(), nullable=False),
        sa.Column('field_changes', sa.Text(), nullable=False),
        sa.Column('old_values', sa.Text(), nullable=False),
        sa.Column('new_values', sa.Text(), nullable=False),
        sa.Column('approval_status', sa.String(length=20), nullable=False),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('approval_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['corrected_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['corrected_submission_id'], ['activity_data.id'], ),
        sa.ForeignKeyConstraint(['original_submission_id'], ['activity_data.id'], ),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('activity_data_corrections')
    op.drop_table('activity_data')
    op.drop_table('emission_factors')
    op.drop_table('material_subtypes')
    op.drop_table('material_categories')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS materialcategory')
    op.execute('DROP TYPE IF EXISTS standardunit')
    op.execute('DROP TYPE IF EXISTS emissionfactortype')
    op.execute('DROP TYPE IF EXISTS dataqualitytier')
