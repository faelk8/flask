"""Legacy schema baseline."""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('jogos', sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('nome', sa.String(50), nullable=False),
                    sa.Column('categoria', sa.String(40), nullable=False),
                    sa.Column('console', sa.String(20), nullable=False))
    op.create_table('usuarios', sa.Column('nickname', sa.String(8), primary_key=True),
                    sa.Column('nome', sa.String(20), nullable=False),
                    sa.Column('senha', sa.String(100), nullable=False))


def downgrade():
    op.drop_table('usuarios')
    op.drop_table('jogos')
