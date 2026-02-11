"""add_holidays_and_working_saturdays_tables

Revision ID: c78e2a86a0da
Revises: e16e9e684c66
Create Date: 2026-02-10 18:57:06.174968

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'c78e2a86a0da'
down_revision = 'e16e9e684c66'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create holidays table
    op.create_table(
        'holidays',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('holiday_date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('is_mandatory', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.Date(), nullable=False),
    )
    op.create_index('ix_holidays_holiday_date', 'holidays', ['holiday_date'], unique=True)
    op.create_index('ix_holidays_year_month', 'holidays', ['holiday_date'])
    
    # Create working_saturdays table
    op.create_table(
        'working_saturdays',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
    )
    op.create_index('ix_working_saturdays_work_date', 'working_saturdays', ['work_date'], unique=True)
    op.create_unique_constraint('uq_working_saturday_month', 'working_saturdays', ['year', 'month'])


def downgrade() -> None:
    op.drop_table('working_saturdays')
    op.drop_table('holidays')
