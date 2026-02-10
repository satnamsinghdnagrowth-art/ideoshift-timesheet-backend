"""add_production_to_task_sub_entries

Revision ID: b1a4172fd748
Revises: e4292785391d
Create Date: 2026-02-09 19:08:44.214067

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1a4172fd748'
down_revision = 'e4292785391d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add production column to task_sub_entries
    op.add_column('task_sub_entries', sa.Column('production', sa.Numeric(10, 2), server_default='0.0', nullable=False))
    
    # Remove server_default after adding the column
    op.alter_column('task_sub_entries', 'production', server_default=None)


def downgrade() -> None:
    # Remove production column
    op.drop_column('task_sub_entries', 'production')
