"""Composition root: framework, adapters and business use cases."""
from functools import wraps
from pathlib import Path
from flask import Flask, g, has_request_context, request
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix
from .application import GameService, AuthService
from .configuration import configure
from .infrastructure import db, SQLGameRepository, SQLUserRepository, BcryptHasher


def create_app(config=None, *, game_service=None, auth_service=None):
    base = Path(__file__).resolve().parent.parent
    app = Flask(__name__, template_folder=str(base / 'templates'), static_folder=str(base / 'static'))
    configure(app, config)
    if app.config['PROXY_HOPS']:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config['PROXY_HOPS'],
                               x_proto=app.config['PROXY_HOPS'], x_host=0, x_port=0, x_prefix=0)
    db.init_app(app)
    Migrate(app, db)
    from .operations import install_observability, ops
    install_observability(app)
    limiter = Limiter(get_remote_address, app=app, application_limits=[app.config['IP_RATE_LIMIT']],
                      default_limits=[], strategy='moving-window')
    app.extensions['rate_limiter'] = limiter
    CSRFProtect(app)
    hasher = BcryptHasher()
    def actor():
        return g.user.nickname if has_request_context() and getattr(g, 'user', None) else 'operator'
    def request_id():
        return getattr(g, 'request_id', None) if has_request_context() else None
    repository = SQLGameRepository(actor, request_id, app.config['COVER_TOTAL_QUOTA'], app.config['COVER_USER_QUOTA'])
    app.extensions['games'] = game_service or GameService(repository)
    app.extensions['auth'] = auth_service or AuthService(SQLUserRepository(), hasher, hasher.hash('dummy-password'))
    from .presentation import web, api, register_errors
    from .security import account_limit_key, current_user
    app.register_blueprint(web)
    app.register_blueprint(api)
    app.register_blueprint(ops)
    # New wrapper per factory instance avoids sharing decorator state between apps.
    def delegate(view):
        @wraps(view, updated=())
        def wrapper(*args, **kwargs):
            return view(*args, **kwargs)
        return wrapper
    for endpoint in ('web.autenticar', 'api.login'):
        view = delegate(app.view_functions[endpoint])
        view = limiter.shared_limit(app.config['LOGIN_ACCOUNT_LIMIT'], scope='login-account', key_func=account_limit_key)(view)
        app.view_functions[endpoint] = limiter.shared_limit(app.config['LOGIN_IP_LIMIT'], scope='login-ip')(view)
    for endpoint in ('api.create_game', 'api.update_game', 'api.delete_game', 'web.criar', 'web.atualizar', 'web.deletar'):
        view = delegate(app.view_functions[endpoint])
        app.view_functions[endpoint] = limiter.shared_limit(app.config['WRITE_RATE_LIMIT'], scope='writes',
            key_func=lambda: 'user:' + current_user().nickname if current_user() else 'ip:' + get_remote_address())(view)
    for endpoint in ('ops.live', 'ops.ready', 'ops.metrics'):
        limiter.exempt(app.view_functions[endpoint])
    register_errors(app)
    from .commands import register_commands
    register_commands(app)
    app.context_processor(lambda: {'current_user': current_user})
    return app
