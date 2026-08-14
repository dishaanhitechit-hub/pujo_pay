"""add cancelled enum value to statusenum

Revision ID: 007877994c33
Revises: fa2280b27422
Create Date: 2026-08-14 16:29:51.403032

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007877994c33'
down_revision = 'fa2280b27422'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE statusenum ADD VALUE IF NOT EXISTS 'cancelled'")


def downgrade():
    pass  # PostgreSQL does not support removing enum values
