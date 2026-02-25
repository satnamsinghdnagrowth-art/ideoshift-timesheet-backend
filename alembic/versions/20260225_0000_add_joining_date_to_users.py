"""Add joining_date column to users table

Revision ID: add_joining_date_to_users
Revises: add_pending_deletion_status
Create Date: 2026-02-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_joining_date_to_users'
down_revision = 'add_pending_deletion_status'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add joining_date column to users table
    op.add_column('users', sa.Column('joining_date', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove joining_date column from users table
    op.drop_column('users', 'joining_date')
