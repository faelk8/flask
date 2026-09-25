"""Enforce unique game names, including concurrent requests."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    duplicates = connection.execute(sa.text('SELECT nome FROM jogos GROUP BY nome HAVING COUNT(*) > 1')).first()
    if duplicates:
        raise RuntimeError('Existem jogos com nomes duplicados. Revise os dados antes de migrar; nada será removido automaticamente.')
    with op.batch_alter_table('jogos') as batch:
        batch.create_unique_constraint('uq_jogos_nome', ['nome'])


def downgrade():
    with op.batch_alter_table('jogos') as batch:
        batch.drop_constraint('uq_jogos_nome', type_='unique')
