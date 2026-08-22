"""add token table

Revision ID: c4d2e8f1a3b6
Revises: 007877994c33
Create Date: 2026-08-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c4d2e8f1a3b6'
down_revision = '007877994c33'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE TYPE IF NOT EXISTS tokentypeenum AS ENUM ('single', 'dual', 'bulk')")
    op.execute("CREATE TYPE IF NOT EXISTS tokenstatusenum AS ENUM ('active', 'void')")

    op.create_table(
        'tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('token_no', sa.String(60), nullable=False, unique=True),
        sa.Column('token_serial', sa.Integer(), nullable=False),
        sa.Column('type', sa.Enum('single', 'dual', 'bulk', name='tokentypeenum', create_type=False), nullable=False),
        sa.Column('status', sa.Enum('active', 'void', name='tokenstatusenum', create_type=False),
                  nullable=False, server_default='active'),
        sa.Column('participant_name', sa.String(120)),
        sa.Column('topic', sa.String(200)),
        sa.Column('org_name', sa.String(200), nullable=False),
        sa.Column('generated_by_id', sa.Integer(),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('generated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('batch_id', sa.String(36)),
    )


def downgrade():
    op.drop_table('tokens')
    op.execute("DROP TYPE IF EXISTS tokentypeenum")
    op.execute("DROP TYPE IF EXISTS tokenstatusenum")
