"""add cancelled payment status

Revision ID: fa2280b27422
Revises: ca259cdbc2ca
Create Date: 2026-08-14 15:14:03.870277

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fa2280b27422'
down_revision = 'ca259cdbc2ca'
branch_labels = None
depends_on = None


def upgrade():
    # Add 'cancelled' to the PostgreSQL enum type (IF NOT EXISTS requires PG 9.6+)
    op.execute("ALTER TYPE statusenum ADD VALUE IF NOT EXISTS 'cancelled'")

    # Add cancelled_at column (column may already exist if added manually)
    conn = op.get_bind()
    cols = [row[0] for row in conn.execute(
        sa.text("SELECT column_name FROM information_schema.columns WHERE table_name='payments'")
    )]
    if 'cancelled_at' not in cols:
        with op.batch_alter_table('payments', schema=None) as batch_op:
            batch_op.add_column(sa.Column('cancelled_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.drop_column('cancelled_at')
    # Note: PostgreSQL does not support removing enum values
