"""Add MRV tables for sample tracking, tests, labs, chain of custody, and event logging

Revision ID: add_mrv_tables
Revises: ba4fe058ab35
Create Date: 2025-12-12 11:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_mrv_tables'
down_revision = 'ba4fe058ab35'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create MRV tables"""
    
    # Create mrv_sample table
    op.create_table('mrv_sample',
        sa.Column('sample_id', sa.String(length=50), nullable=False, primary_key=True),
        sa.Column('project_id', sa.String(length=36), sa.ForeignKey('project.id'), nullable=False),
        sa.Column('collected_by', sa.String(length=255), nullable=False),
        sa.Column('collected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('geotag_lat', sa.Numeric(precision=10, scale=8), nullable=False),
        sa.Column('geotag_lon', sa.Numeric(precision=11, scale=8), nullable=False),
        sa.Column('sample_type', sa.String(length=100), nullable=False),
        sa.Column('chain_of_custody', sa.JSON(), server_default='{}'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('collected', 'submitted', 'in_lab', 'tested', 'approved', 'rejected', name='mrv_sample_status'), nullable=False, server_default='collected'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('sample_id')
    )
    
    # Create indexes for mrv_sample
    op.create_index('idx_mrv_sample_project_id', 'mrv_sample', ['project_id'])
    op.create_index('idx_mrv_sample_status', 'mrv_sample', ['status'])
    op.create_index('idx_mrv_sample_collected_at', 'mrv_sample', ['collected_at'])
    
    # Create lab table
    op.create_table('lab',
        sa.Column('lab_id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('address', sa.Text(), nullable=False),
        sa.Column('accreditation', sa.String(length=100), nullable=True),
        sa.Column('contact', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('lab_id')
    )
    
    # Create mrv_test table
    op.create_table('mrv_test',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('sample_id', sa.String(length=50), sa.ForeignKey('mrv_sample.sample_id'), nullable=False),
        sa.Column('lab_id', sa.String(length=36), sa.ForeignKey('lab.lab_id'), nullable=False),
        sa.Column('parameter', sa.String(length=255), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('method', sa.String(length=255), nullable=False),
        sa.Column('certificate_file', sa.String(length=512), nullable=True),
        sa.Column('lab_report_id', sa.String(length=100), nullable=True),
        sa.Column('passed', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for mrv_test
    op.create_index('idx_mrv_test_sample_id', 'mrv_test', ['sample_id'])
    op.create_index('idx_mrv_test_lab_id', 'mrv_test', ['lab_id'])
    op.create_index('idx_mrv_test_parameter', 'mrv_test', ['parameter'])
    
    # Create chain_step table
    op.create_table('chain_step',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('sample_id', sa.String(length=50), sa.ForeignKey('mrv_sample.sample_id'), nullable=False),
        sa.Column('actor', sa.String(length=255), nullable=False),
        sa.Column('action', sa.String(length=255), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('evidence_file', sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for chain_step
    op.create_index('idx_chain_step_sample_id', 'chain_step', ['sample_id'])
    op.create_index('idx_chain_step_timestamp', 'chain_step', ['timestamp'])
    
    # Create mrv_event_log table
    op.create_table('mrv_event_log',
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),
        sa.Column('ref_type', sa.String(length=50), nullable=False),
        sa.Column('ref_id', sa.String(length=50), nullable=False),
        sa.Column('event', sa.String(length=255), nullable=False),
        sa.Column('actor', sa.String(length=255), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('details', sa.JSON(), server_default='{}'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for mrv_event_log
    op.create_index('idx_mrv_event_log_ref', 'mrv_event_log', ['ref_type', 'ref_id'])
    op.create_index('idx_mrv_event_log_ts', 'mrv_event_log', ['ts'])
    op.create_index('idx_mrv_event_log_event', 'mrv_event_log', ['event'])


def downgrade() -> None:
    """Remove MRV tables"""
    
    # Drop indexes first
    op.drop_index('idx_mrv_event_log_event', table_name='mrv_event_log')
    op.drop_index('idx_mrv_event_log_ts', table_name='mrv_event_log')
    op.drop_index('idx_mrv_event_log_ref', table_name='mrv_event_log')
    op.drop_index('idx_chain_step_timestamp', table_name='chain_step')
    op.drop_index('idx_chain_step_sample_id', table_name='chain_step')
    op.drop_index('idx_mrv_test_parameter', table_name='mrv_test')
    op.drop_index('idx_mrv_test_lab_id', table_name='mrv_test')
    op.drop_index('idx_mrv_test_sample_id', table_name='mrv_test')
    op.drop_index('idx_mrv_sample_collected_at', table_name='mrv_sample')
    op.drop_index('idx_mrv_sample_status', table_name='mrv_sample')
    op.drop_index('idx_mrv_sample_project_id', table_name='mrv_sample')
    
    # Drop tables
    op.drop_table('mrv_event_log')
    op.drop_table('chain_step')
    op.drop_table('mrv_test')
    op.drop_table('lab')
    op.drop_table('mrv_sample')
