"""add_trial_management_and_report_template

Revision ID: 002
Revises: 001
Create Date: 2025-03-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to users table for trial management
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('company_name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('reports_generated_count', sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('max_reports_trial', sa.Integer(), nullable=True, server_default='10'))
        batch_op.add_column(sa.Column('templates_saved_count', sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('max_templates_trial', sa.Integer(), nullable=True, server_default='3'))
        batch_op.add_column(sa.Column('files_uploaded_count', sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('max_files_trial', sa.Integer(), nullable=True, server_default='5'))
        batch_op.add_column(sa.Column('last_report_generated_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('daily_report_count', sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('daily_report_reset_date', sa.Date(), nullable=True))
    
    # Create report_templates table
    op.create_table('report_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_config', sa.JSON(), nullable=False),
        sa.Column('source_file_structure', sa.JSON(), nullable=True),
        sa.Column('times_used', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index on user_id for faster lookups
    op.create_index('ix_report_templates_user_id', 'report_templates', ['user_id'])


def downgrade() -> None:
    # Drop report_templates table
    op.drop_index('ix_report_templates_user_id', table_name='report_templates')
    op.drop_table('report_templates')
    
    # Remove columns from users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('daily_report_reset_date')
        batch_op.drop_column('daily_report_count')
        batch_op.drop_column('last_report_generated_at')
        batch_op.drop_column('max_files_trial')
        batch_op.drop_column('files_uploaded_count')
        batch_op.drop_column('max_templates_trial')
        batch_op.drop_column('templates_saved_count')
        batch_op.drop_column('max_reports_trial')
        batch_op.drop_column('reports_generated_count')
        batch_op.drop_column('trial_ends_at')
        batch_op.drop_column('company_name')
