"""Database and password adapters. Mutations and their audit records commit together."""
import hashlib
import json
import time
from dataclasses import asdict
import bcrypt
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select, func, delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import deferred
from sqlalchemy.dialects.mysql import MEDIUMBLOB
from .domain import Game, User, Conflict, NotFound, QuotaExceeded

db = SQLAlchemy()


class GameModel(db.Model):
    __tablename__ = "jogos"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False, unique=True)
    categoria = db.Column(db.String(40), nullable=False)
    console = db.Column(db.String(20), nullable=False)


class UserModel(db.Model):
    __tablename__ = "usuarios"
    nickname = db.Column(db.String(8), primary_key=True)
    nome = db.Column(db.String(20), nullable=False)
    senha = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="viewer", server_default="viewer")
    active = db.Column(db.Boolean, nullable=False, default=True, server_default="1")
    totp_secret = db.Column(db.String(255))
    totp_last_step = db.Column(db.BigInteger, nullable=False, default=-1, server_default="-1")
    __table_args__ = (db.CheckConstraint("role IN ('viewer','editor','admin')", name="ck_user_role"),)


class AuthSession(db.Model):
    __tablename__ = "auth_sessions"
    token_hash = db.Column(db.String(64), primary_key=True)
    nickname = db.Column(db.String(8), nullable=False, index=True)
    expires_at = db.Column(db.BigInteger, nullable=False, index=True)
    last_seen = db.Column(db.BigInteger, nullable=False)


class AuditEvent(db.Model):
    __tablename__ = "audit_events"
    id = db.Column(db.Integer, primary_key=True)
    occurred_at = db.Column(db.BigInteger, nullable=False, default=lambda: int(time.time()), index=True)
    actor = db.Column(db.String(32), nullable=False)
    action = db.Column(db.String(40), nullable=False)
    resource = db.Column(db.String(100), nullable=False)
    request_id = db.Column(db.String(32))


class CoverModel(db.Model):
    __tablename__ = "covers"
    game_id = db.Column(db.Integer, db.ForeignKey("jogos.id"), primary_key=True)
    owner = db.Column(db.String(32), nullable=False, index=True)
    content = deferred(db.Column(db.LargeBinary().with_variant(MEDIUMBLOB(), 'mysql'), nullable=False))
    size = db.Column(db.Integer, nullable=False)
    digest = db.Column(db.String(64), nullable=False)


class StorageQuota(db.Model):
    __tablename__ = "storage_quota"
    id = db.Column(db.Integer, primary_key=True)
    used_bytes = db.Column(db.BigInteger, nullable=False, default=0)


class IdempotencyRecord(db.Model):
    __tablename__ = "idempotency_records"
    actor = db.Column(db.String(32), primary_key=True)
    key = db.Column(db.String(128), primary_key=True)
    fingerprint = db.Column(db.String(64), nullable=False)
    response = db.Column(db.Text, nullable=False)
    expires_at = db.Column(db.BigInteger, nullable=False, index=True)


def audit(actor, action, resource, request_id=None):
    db.session.add(AuditEvent(actor=actor, action=action, resource=str(resource), request_id=request_id))


def entity(row):
    return Game(row.id, row.nome, row.categoria, row.console)


class SQLGameRepository:
    def __init__(self, actor=lambda: "system", request_id=lambda: None,
                 total_quota=100 * 1024 * 1024, user_quota=10 * 1024 * 1024):
        self.actor, self.request_id = actor, request_id
        self.total_quota, self.user_quota = total_quota, user_quota

    def list(self, page, per_page):
        total = db.session.scalar(select(func.count()).select_from(GameModel))
        rows = db.session.scalars(select(GameModel).order_by(GameModel.id)
                                  .offset((page - 1) * per_page).limit(per_page))
        return [entity(row) for row in rows], total

    def cursor(self, after, limit):
        return [entity(row) for row in db.session.scalars(
            select(GameModel).where(GameModel.id > after).order_by(GameModel.id).limit(limit))]

    def get(self, game_id):
        row = db.session.get(GameModel, game_id)
        return entity(row) if row else None

    def _replay(self, key, fingerprint):
        if not key:
            return None
        record = db.session.get(IdempotencyRecord, (self.actor(), key))
        if record and record.expires_at > time.time():
            if record.fingerprint != fingerprint:
                raise Conflict("Idempotency-Key já utilizada com outro conteúdo.")
            return Game(**json.loads(record.response))
        if record:
            db.session.delete(record)
            db.session.flush()
        return None

    def _lock_storage(self):
        # An UPDATE acquires the writer lock on SQLite and a row lock on MySQL.
        result = db.session.execute(update(StorageQuota).where(StorageQuota.id == 1)
                                    .values(used_bytes=StorageQuota.used_bytes))
        if result.rowcount != 1:
            raise RuntimeError("Execute as migrações para inicializar a cota de armazenamento.")
        return db.session.get(StorageQuota, 1, populate_existing=True)

    def _save_cover(self, game_id, content):
        quota = self._lock_storage()
        old = db.session.get(CoverModel, game_id)
        old_size = old.size if old else 0
        used = db.session.scalar(select(func.coalesce(func.sum(CoverModel.size), 0))
                                 .where(CoverModel.owner == self.actor()))
        user_delta = len(content) - (old_size if old and old.owner == self.actor() else 0)
        if quota.used_bytes + len(content) - old_size > self.total_quota or used + user_delta > self.user_quota:
            raise QuotaExceeded("Cota de armazenamento de capas excedida.")
        quota.used_bytes += len(content) - old_size
        row = old or CoverModel(game_id=game_id)
        row.owner, row.content, row.size = self.actor(), content, len(content)
        row.digest = hashlib.sha256(content).hexdigest()
        db.session.add(row)

    def save(self, fields, game_id=None, *, cover=None, idempotency_key=None):
        fingerprint = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
        try:
            replay = self._replay(idempotency_key, fingerprint)
            if replay:
                return replay
            duplicate = db.session.scalar(select(GameModel).where(GameModel.nome == fields["nome"]))
            if duplicate and duplicate.id != game_id:
                raise Conflict("Jogo já cadastrado.")
            row = db.session.get(GameModel, game_id) if game_id else GameModel()
            if row is None:
                raise NotFound("Jogo não encontrado.")
            for key, value in fields.items():
                setattr(row, key, value)
            db.session.add(row)
            db.session.flush()
            if cover is not None:
                self._save_cover(row.id, cover)
            result = entity(row)
            audit(self.actor(), "game.update" if game_id else "game.create", row.id, self.request_id())
            if idempotency_key:
                db.session.add(IdempotencyRecord(actor=self.actor(), key=idempotency_key,
                    fingerprint=fingerprint, response=json.dumps(asdict(result)), expires_at=int(time.time()) + 86400))
            db.session.commit()
            return result
        except IntegrityError:
            db.session.rollback()
            replay = self._replay(idempotency_key, fingerprint)
            if replay:
                return replay
            raise Conflict("Jogo já cadastrado ou operação concorrente conflitante.") from None
        except Exception:
            db.session.rollback()
            raise

    def delete(self, game_id):
        try:
            quota = self._lock_storage()
            row = db.session.get(GameModel, game_id)
            if row is None:
                raise NotFound("Jogo não encontrado.")
            cover = db.session.get(CoverModel, game_id)
            if cover:
                quota.used_bytes -= cover.size
                db.session.delete(cover)
                db.session.flush()
            db.session.delete(row)
            audit(self.actor(), "game.delete", game_id, self.request_id())
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise


class SQLUserRepository:
    def get(self, nickname):
        row = db.session.get(UserModel, nickname)
        return User(row.nickname, row.senha, row.role, row.active, bool(row.totp_secret)) if row else None


class BcryptHasher:
    def hash(self, password):
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def verify(self, password, hashed):
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except (ValueError, TypeError):
            return False
