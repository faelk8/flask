"""Environment configuration, with fail-closed production validation."""
import os
from datetime import timedelta
from pathlib import Path
from cryptography.fernet import Fernet
from sqlalchemy.engine import make_url


def configure(app, overrides):
    base = Path(__file__).resolve().parent.parent
    production = os.getenv('APP_ENV', 'development') == 'production'
    uri = os.getenv('DATABASE_URL', 'sqlite:///jogoteca.db')
    engine = {'pool_pre_ping': True, 'pool_recycle': 300, 'hide_parameters': True}
    if uri.startswith('mysql'):
        engine.update(pool_size=int(os.getenv('DB_POOL_SIZE', '5')),
                      max_overflow=int(os.getenv('DB_MAX_OVERFLOW', '5')), pool_timeout=5,
                      connect_args={'connection_timeout': 5, 'read_timeout': 10, 'write_timeout': 10})
    app.config.from_mapping(
        PRODUCTION=production, SECRET_KEY=os.getenv('SECRET_KEY'), DEBUG=False,
        SQLALCHEMY_DATABASE_URI=uri, SQLALCHEMY_ENGINE_OPTIONS=engine,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=production,
        SESSION_REFRESH_EACH_REQUEST=False, PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
        AUTH_SESSION_SECONDS=3600, AUTH_IDLE_SECONDS=900,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024, MAX_FORM_MEMORY_SIZE=100000, MAX_FORM_PARTS=20,
        UPLOAD_PATH=str(base / 'uploads'), DEFAULT_COVER=str(base / 'uploads' / 'capa_padrao.jpg'),
        COVER_TOTAL_QUOTA=int(os.getenv('COVER_TOTAL_QUOTA', str(100 * 1024 * 1024))),
        COVER_USER_QUOTA=int(os.getenv('COVER_USER_QUOTA', str(10 * 1024 * 1024))),
        RATELIMIT_STORAGE_URI=os.getenv('RATELIMIT_STORAGE_URI', 'memory://'),
        RATELIMIT_HEADERS_ENABLED=True, RATELIMIT_SWALLOW_ERRORS=False,
        RATELIMIT_STORAGE_OPTIONS={'socket_connect_timeout': 2, 'socket_timeout': 2} if os.getenv('RATELIMIT_STORAGE_URI', '').startswith('redis') else {},
        IP_RATE_LIMIT=os.getenv('IP_RATE_LIMIT', '300 per minute'),
        LOGIN_IP_LIMIT=os.getenv('LOGIN_IP_LIMIT', '5 per minute'),
        LOGIN_ACCOUNT_LIMIT=os.getenv('LOGIN_ACCOUNT_LIMIT', '10 per minute'),
        WRITE_RATE_LIMIT=os.getenv('WRITE_RATE_LIMIT', '30 per minute'),
        PROXY_HOPS=int(os.getenv('PROXY_HOPS', '0')),
        TRUSTED_HOSTS=[h.strip() for h in os.getenv('TRUSTED_HOSTS', '').split(',') if h.strip()] or None,
        MFA_ENCRYPTION_KEY=os.getenv('MFA_ENCRYPTION_KEY'), REQUIRE_ADMIN_MFA=production,
        METRICS_TOKEN=os.getenv('METRICS_TOKEN'),
    )
    app.config.update(overrides or {})
    if not isinstance(app.config['SECRET_KEY'], str) or len(app.config['SECRET_KEY']) < 32:
        raise RuntimeError('Configure SECRET_KEY com pelo menos 32 caracteres aleatórios.')
    if app.config['MFA_ENCRYPTION_KEY']:
        Fernet(app.config['MFA_ENCRYPTION_KEY'].encode())
    if not 0 <= app.config['PROXY_HOPS'] <= 2:
        raise RuntimeError('PROXY_HOPS deve ser 0, 1 ou 2, conforme a topologia documentada.')
    if app.config['COVER_USER_QUOTA'] <= 0 or app.config['COVER_TOTAL_QUOTA'] < app.config['COVER_USER_QUOTA']:
        raise RuntimeError('As cotas devem ser positivas e a cota global deve cobrir a individual.')
    if app.config['PRODUCTION']:
        database = make_url(app.config['SQLALCHEMY_DATABASE_URI'])
        valid = (database.drivername.startswith('mysql') and database.username not in (None, 'root')
                 and app.config['RATELIMIT_STORAGE_URI'].startswith(('redis://', 'rediss://'))
                 and app.config['TRUSTED_HOSTS'] and app.config['MFA_ENCRYPTION_KEY']
                 and len(app.config['METRICS_TOKEN'] or '') >= 32
                 and app.config['SESSION_COOKIE_SECURE'] and app.config['REQUIRE_ADMIN_MFA']
                 and not app.config['DEBUG'] and not app.config.get('TESTING'))
        if not valid:
            raise RuntimeError('Produção exige MySQL sem root, Redis, TRUSTED_HOSTS, MFA_ENCRYPTION_KEY, METRICS_TOKEN e proteções ativas.')
