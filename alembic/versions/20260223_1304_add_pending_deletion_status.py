"""Add PENDING_DELETION status and deletion request fields to task entries

Revision ID: add_pending_deletion_status
Revises: add_supervisor_role
Create Date: 2026-02-23 13:04:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_pending_deletion_status'
down_revision = 'add_supervisor_role'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Modify ENUM column to add PENDING_DELETION to task_entries.status
    op.execute(
        "ALTER TABLE task_entries MODIFY COLUMN status "
        "ENUM('DRAFT','PENDING','APPROVED','REJECTED','PENDING_DELETION') NOT NULL"
    )

    # 2. Add new columns for deletion request tracking
    op.add_column(
        'task_entries',
        sa.Column('deletion_reason', sa.String(500), nullable=True)
    )
    op.add_column(
        'task_entries',
        sa.Column('deletion_requested_at', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'task_entries',
        sa.Column('pre_deletion_status',
                  sa.Enum('DRAFT', 'PENDING', 'APPROVED', 'REJECTED', 'PENDING_DELETION'),
                  nullable=True)
    )


def downgrade() -> None:
    # 1. Remove new columns
    op.drop_column('task_entries', 'pre_deletion_status')
    op.drop_column('task_entries', 'deletion_requested_at')
    op.drop_column('task_entries', 'deletion_reason')

    # 2. Restore ENUM column to original values (remove PENDING_DELETION)
    op.execute(
        "ALTER TABLE task_entries MODIFY COLUMN status "
        "ENUM('DRAFT','PENDING','APPROVED','REJECTED') NOT NULL"
    )
