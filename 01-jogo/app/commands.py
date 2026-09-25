"""Administrative commands accessible only to the deployment operator."""
import json
import time
from pathlib import Path
import click
import pyotp
from flask import current_app
from sqlalchemy import select, delete
from .infrastructure import (db, UserModel, AuthSession, StorageQuota, AuditEvent,
                             IdempotencyRecord, BcryptHasher, CoverModel, GameModel, audit)
from .security import cipher


def get_user(nickname):
    user = db.session.get(UserModel, nickname)
    if not user:
        raise click.ClickException('Usuário não encontrado.')
    return user


def password_hash(password):
    if len(password) < 12 or len(password.encode()) > 72:
        raise click.ClickException('Senha: mínimo de 12 caracteres e máximo de 72 bytes.')
    return BcryptHasher().hash(password)


def invalidate(nickname):
    db.session.execute(delete(AuthSession).where(AuthSession.nickname == nickname))


def register_commands(app):
    @app.cli.command('init-db')
    def init_db():
        """Development only. Production schemas must use migrations."""
        if app.config['PRODUCTION']:
            raise click.ClickException('Em produção use flask db upgrade.')
        db.create_all()
        if not db.session.get(StorageQuota, 1):
            db.session.add(StorageQuota(id=1, used_bytes=0))
        db.session.commit()
        click.echo('Tabelas ausentes criadas; nenhum dado apagado.')

    @app.cli.command('create-user')
    @click.option('--nickname', prompt=True)
    @click.option('--name', prompt=True)
    @click.option('--role', type=click.Choice(['viewer', 'editor', 'admin']), default='viewer', show_default=True)
    @click.password_option()
    def create_user(nickname, name, role, password):
        if not 1 <= len(nickname) <= 8 or not 1 <= len(name.strip()) <= 20:
            raise click.ClickException('Nickname: 1–8 caracteres; nome: 1–20.')
        if db.session.get(UserModel, nickname):
            raise click.ClickException('Usuário já existe.')
        db.session.add(UserModel(nickname=nickname, nome=name.strip(), senha=password_hash(password), role=role))
        audit('operator', 'user.create', nickname)
        db.session.commit()
        click.echo('Usuário criado. Administrador em produção exige configure-mfa antes do login.')

    @app.cli.command('manage-user')
    @click.argument('nickname')
    @click.option('--role', type=click.Choice(['viewer', 'editor', 'admin']))
    @click.option('--active/--inactive', default=None)
    def manage_user(nickname, role, active):
        user = get_user(nickname)
        if role is None and active is None:
            raise click.UsageError('Informe --role, --active ou --inactive.')
        if role is not None:
            user.role = role
        if active is not None:
            user.active = active
        invalidate(nickname)
        audit('operator', 'user.permissions', nickname)
        db.session.commit()
        click.echo('Permissões atualizadas; sessões revogadas.')

    @app.cli.command('revoke-sessions')
    @click.argument('nickname')
    def revoke_sessions(nickname):
        get_user(nickname)
        invalidate(nickname)
        audit('operator', 'auth.revoke', nickname)
        db.session.commit()
        click.echo('Sessões revogadas.')

    @app.cli.command('reset-password')
    @click.argument('nickname')
    @click.password_option()
    def reset_password(nickname, password):
        user = get_user(nickname)
        user.senha = password_hash(password)
        invalidate(nickname)
        audit('operator', 'user.password_reset', nickname)
        db.session.commit()
        click.echo('Senha atualizada; sessões revogadas.')

    @app.cli.command('configure-mfa')
    @click.argument('nickname')
    def configure_mfa(nickname):
        """Enroll/re-enroll via a trusted terminal. Confirm possession before replacing a secret."""
        user = get_user(nickname)
        if not app.config['MFA_ENCRYPTION_KEY']:
            raise click.ClickException('Configure MFA_ENCRYPTION_KEY (Fernet) primeiro.')
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        click.echo('Importe esta URI no autenticador, em canal privado. Não salve em logs:')
        click.echo(totp.provisioning_uri(name=nickname, issuer_name='Jogoteca'))
        code = click.prompt('Código do autenticador', hide_input=True)
        if not totp.verify(code, valid_window=0):
            raise click.ClickException('Código inválido; configuração anterior preservada.')
        user.totp_secret = cipher().encrypt(secret.encode()).decode()
        user.totp_last_step = int(time.time()) // 30
        invalidate(nickname)
        audit('operator', 'auth.mfa_enroll', nickname)
        db.session.commit()
        click.echo('Segundo fator ativado. Aguarde o próximo código para entrar.')

    @app.cli.command('maintenance')
    @click.option('--apply', is_flag=True, help='Sem esta opção apenas conta registros expirados.')
    def maintenance(apply):
        now = int(time.time())
        queries = [(AuthSession, (AuthSession.expires_at < now) | (AuthSession.last_seen < now - app.config['AUTH_IDLE_SECONDS'])),
                   (IdempotencyRecord, IdempotencyRecord.expires_at < now),
                   (AuditEvent, AuditEvent.occurred_at < now - 90 * 86400)]
        for model, predicate in queries:
            count = db.session.query(model).filter(predicate).count()
            click.echo(f'{model.__tablename__}: {count} registros elegíveis')
            if apply:
                db.session.execute(delete(model).where(predicate))
        if apply:
            audit('operator', 'maintenance.prune', 'expired records')
            db.session.commit()

    @app.cli.command('audit-export')
    @click.option('--after', type=click.IntRange(min=0), default=0)
    @click.option('--limit', type=click.IntRange(1, 10000), default=1000)
    def audit_export(after, limit):
        for row in db.session.scalars(select(AuditEvent).where(AuditEvent.id > after).order_by(AuditEvent.id).limit(limit)):
            click.echo(json.dumps({key: getattr(row, key) for key in ('id', 'occurred_at', 'actor', 'action', 'resource', 'request_id')}))

    @app.cli.command('import-covers')
    @click.argument('directory', type=click.Path(exists=True, file_okay=False, path_type=Path))
    def import_covers(directory):
        """Import legacy JPEGs into the database, preserving originals on disk."""
        from werkzeug.datastructures import FileStorage
        from .covers import read_cover
        for game in db.session.scalars(select(GameModel).order_by(GameModel.id)):
            if db.session.get(CoverModel, game.id):
                continue
            paths = sorted(directory.glob(f'capa{game.id}-*.jpg'))
            if not paths:
                continue
            path = paths[-1]
            if path.is_symlink() or path.stat().st_size > app.config['MAX_CONTENT_LENGTH']:
                raise click.ClickException(f'Arquivo recusado: {path.name}')
            with path.open('rb') as source:
                content = read_cover(FileStorage(source, filename=path.name))
            app.extensions['games'].update(game.id, {'nome': game.nome, 'categoria': game.categoria, 'console': game.console}, cover=content)
            click.echo(f'Capa importada: jogo {game.id}')
