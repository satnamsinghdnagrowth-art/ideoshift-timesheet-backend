"""Add SUPERVISOR role to UserRole enum

Revision ID: add_supervisor_role
Revises: 010e711d9e1d
Create Date: 2026-02-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_supervisor_role'
down_revision = '010e711d9e1d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MySQL specific: Modify the ENUM column to add SUPERVISOR
    op.execute("ALTER TABLE users MODIFY role ENUM('ADMIN', 'EMPLOYEE', 'SUPERVISOR') NOT NULL DEFAULT 'EMPLOYEE'")


def downgrade() -> None:
    # MySQL specific: Remove SUPERVISOR from ENUM (if downgrading)
    op.execute("ALTER TABLE users MODIFY role ENUM('ADMIN', 'EMPLOYEE') NOT NULL DEFAULT 'EMPLOYEE'")
