"""rename junior_secretary -> joint_secretary in existing rows

Revision ID: f1a2b3c4d5e6
Revises: e2fd54867b4e
Create Date: 2026-10-07 00:00:00.000000

"""
from alembic import op

revision = 'f1a2b3c4d5e6'
down_revision = 'e2fd54867b4e'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE year_role_assignments SET role = 'joint_secretary' WHERE role = 'junior_secretary'"
    )
    op.execute(
        "UPDATE event_role_assignments SET role = 'joint_secretary' WHERE role = 'junior_secretary'"
    )


def downgrade():
    op.execute(
        "UPDATE year_role_assignments SET role = 'junior_secretary' WHERE role = 'joint_secretary'"
    )
    op.execute(
        "UPDATE event_role_assignments SET role = 'junior_secretary' WHERE role = 'joint_secretary'"
    )
