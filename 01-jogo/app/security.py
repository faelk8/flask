"""Server-side session and TOTP adapters; no secrets are written to logs."""
import hashlib
import hmac
import secrets
import time
from functools import wraps
import pyotp
from cryptography.fernet import Fernet
from flask import current_app, g, request, session
from sqlalchemy import select, delete, update
from .domain import Unauthorized, Forbidden
from .infrastructure import db, UserModel, AuthSession, audit


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def cipher():
    return Fernet(current_app.config['MFA_ENCRYPTION_KEY'].encode())


def verify_second_factor(user, code):
    row = db.session.get(UserModel, user.nickname)
    if not row.totp_secret:
        if user.role == 'admin' and current_app.config['REQUIRE_ADMIN_MFA']:
            raise Unauthorized('Credenciais inválidas ou segundo fator necessário.')
        return
    if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
        raise Unauthorized('Credenciais inválidas ou segundo fator necessário.')
    totp = pyotp.TOTP(cipher().decrypt(row.totp_secret.encode()).decode())
    now = int(time.time()) // 30
    matched = next((step for step in (now - 1, now, now + 1)
                    if hmac.compare_digest(totp.at(step * 30), code)), None)
    if matched is None:
        raise Unauthorized('Credenciais inválidas ou segundo fator necessário.')
    result = db.session.execute(update(UserModel).where(UserModel.nickname == user.nickname,
                                UserModel.totp_last_step < matched).values(totp_last_step=matched))
    if result.rowcount != 1:
        db.session.rollback()
        raise Unauthorized('Credenciais inválidas ou segundo fator necessário.')


def start_session(user, code=None):
    verify_second_factor(user, code)
    now = int(time.time())
    # Serialize session creation for the same account on the production database.
    db.session.execute(update(UserModel).where(UserModel.nickname == user.nickname)
                       .values(active=UserModel.active))
    previous = session.get('auth_token')
    if previous:
        db.session.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(previous)))
    rows = list(db.session.scalars(select(AuthSession).where(AuthSession.nickname == user.nickname)
                                  .order_by(AuthSession.last_seen.desc())))
    for row in rows[4:]:
        db.session.delete(row)
    token = secrets.token_urlsafe(32)
    db.session.add(AuthSession(token_hash=token_hash(token), nickname=user.nickname,
                              expires_at=now + current_app.config['AUTH_SESSION_SECONDS'], last_seen=now))
    audit(user.nickname, 'auth.login', user.nickname, getattr(g, 'request_id', None))
    db.session.commit()
    session.clear()
    session['auth_token'] = token
    session['usuario_logado'] = user.nickname  # display only, never used for authorization
    session.permanent = True


def current_user():
    if hasattr(g, 'user'):
        return g.user
    g.user = None
    token = session.get('auth_token')
    if not isinstance(token, str):
        return None
    record = db.session.get(AuthSession, token_hash(token))
    now = int(time.time())
    if not record or record.expires_at <= now or record.last_seen + current_app.config['AUTH_IDLE_SECONDS'] <= now:
        session.clear()
        return None
    user = db.session.get(UserModel, record.nickname)
    if not user or not user.active:
        session.clear()
        return None
    if now - record.last_seen >= 60:
        record.last_seen = now
        db.session.commit()
    g.user = user
    return user


def require_roles(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                raise Unauthorized('Autenticação necessária.')
            if roles and user.role not in roles:
                raise Forbidden('Seu perfil não permite esta operação.')
            return view(*args, **kwargs)
        return wrapped
    return decorator


def end_session():
    token = session.get('auth_token')
    user = current_user()
    if token:
        db.session.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(token)))
    if user:
        audit(user.nickname, 'auth.logout', user.nickname, getattr(g, 'request_id', None))
    db.session.commit()
    session.clear()


def account_limit_key():
    data = request.get_json(silent=True) if request.is_json else request.form
    nickname = data.get('nickname', '') if isinstance(data, dict) or hasattr(data, 'get') else ''
    nickname = str(nickname)[:128].strip().lower()
    return hmac.new(current_app.secret_key.encode(), nickname.encode(), hashlib.sha256).hexdigest()
