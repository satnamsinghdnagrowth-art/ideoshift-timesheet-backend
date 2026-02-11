"""add_status_to_clients

Revision ID: 8b5d3dfc8de2
Revises: c78e2a86a0da
Create Date: 2026-02-11 11:49:01.488778

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8b5d3dfc8de2'
down_revision = 'c78e2a86a0da'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum type
    client_status = postgresql.ENUM('ACTIVE', 'INACTIVE', 'BACKLOG', 'DEMO', name='clientstatus')
    client_status.create(op.get_bind())
    
    # Add status column with default ACTIVE
    op.add_column('clients', sa.Column('status', client_status, nullable=False, server_default='ACTIVE'))


def downgrade() -> None:
    op.drop_column('clients', 'status')
    
    # Drop enum type
    client_status = postgresql.ENUM('ACTIVE', 'INACTIVE', 'BACKLOG', 'DEMO', name='clientstatus')
    client_status.drop(op.get_bind())
