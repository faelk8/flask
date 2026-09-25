"""production_controls

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-25 16:56:12.122443

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('occurred_at', sa.BigInteger(), nullable=False),
    sa.Column('actor', sa.String(length=32), nullable=False),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('resource', sa.String(length=100), nullable=False),
    sa.Column('request_id', sa.String(length=32), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_events_occurred_at'), ['occurred_at'], unique=False)

    op.create_table('idempotency_records',
    sa.Column('actor', sa.String(length=32), nullable=False),
    sa.Column('key', sa.String(length=128), nullable=False),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('response', sa.Text(), nullable=False),
    sa.Column('expires_at', sa.BigInteger(), nullable=False),
    sa.PrimaryKeyConstraint('actor', 'key')
    )
    with op.batch_alter_table('idempotency_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_idempotency_records_expires_at'), ['expires_at'], unique=False)

    op.create_table('storage_quota',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('used_bytes', sa.BigInteger(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('auth_sessions',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('nickname', sa.String(length=8), nullable=False),
    sa.Column('expires_at', sa.BigInteger(), nullable=False),
    sa.Column('last_seen', sa.BigInteger(), nullable=False),
    sa.PrimaryKeyConstraint('token_hash')
    )
    with op.batch_alter_table('auth_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_auth_sessions_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_auth_sessions_nickname'), ['nickname'], unique=False)

    op.create_table('covers',
    sa.Column('game_id', sa.Integer(), nullable=False),
    sa.Column('owner', sa.String(length=32), nullable=False),
    sa.Column('content', sa.LargeBinary().with_variant(mysql.MEDIUMBLOB(), 'mysql'), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('digest', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['game_id'], ['jogos.id'], ),
    sa.PrimaryKeyConstraint('game_id')
    )
    with op.batch_alter_table('covers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_covers_owner'), ['owner'], unique=False)

    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=10), server_default='viewer', nullable=False))
        batch_op.add_column(sa.Column('active', sa.Boolean(), server_default='1', nullable=False))
        batch_op.add_column(sa.Column('totp_secret', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('totp_last_step', sa.BigInteger(), server_default='-1', nullable=False))
        batch_op.create_check_constraint('ck_user_role', "role IN ('viewer','editor','admin')")
    op.execute(sa.text('INSERT INTO storage_quota (id, used_bytes) VALUES (1, 0)'))



def downgrade():
    raise RuntimeError("Esta revisão contém capas e auditoria. Restaure um backup verificado em banco separado; downgrade destrutivo bloqueado.")
