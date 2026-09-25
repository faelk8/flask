"""HTTP adapters: translate requests and use-case results without business rules."""
from dataclasses import asdict
from uuid import uuid4
import re
from io import BytesIO
from flask import (Blueprint, current_app, request, session, jsonify, render_template,
                   redirect, url_for, send_file, g)
from flask_wtf import FlaskForm
from flask_wtf.csrf import generate_csrf
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Optional
from werkzeug.exceptions import HTTPException, BadRequest
from redis.exceptions import RedisError
from sqlalchemy.exc import OperationalError, TimeoutError as DatabaseTimeout
from .domain import DomainError, ValidationError, NotFound, Conflict, Unauthorized, Forbidden, QuotaExceeded
from .infrastructure import db, CoverModel
from .covers import read_cover
from .security import require_roles, start_session, end_session, current_user

web = Blueprint('web', __name__)
api = Blueprint('api', __name__, url_prefix='/api/v1')


def games():
    return current_app.extensions['games']


class GameForm(FlaskForm):
    nome = StringField('Nome do jogo', validators=[DataRequired(), Length(max=50)])
    categoria = StringField('Categoria', validators=[DataRequired(), Length(max=40)])
    console = StringField('Console', validators=[DataRequired(), Length(max=20)])
    salvar = SubmitField('Salvar')


class LoginForm(FlaskForm):
    nickname = StringField('Nickname', validators=[DataRequired(), Length(max=8)])
    senha = PasswordField('Senha', validators=[DataRequired(), Length(max=72)])
    otp = StringField('Código do autenticador (se habilitado)', validators=[Optional(), Length(min=6, max=6)])
    login = SubmitField('Entrar')


def payload():
    data = request.get_json()
    if not isinstance(data, dict):
        raise ValidationError('Envie um objeto JSON.')
    return data


def sign_in(nickname, password, otp=None):
    user = current_app.extensions['auth'].authenticate(nickname, password)
    start_session(user, otp)
    return user


@api.get('/csrf')
def csrf_token():
    return jsonify(csrf_token=generate_csrf())


@api.post('/auth/login')
def login():
    data = payload()
    user = sign_in(data.get('nickname'), data.get('senha'), data.get('otp'))
    return jsonify(data={'nickname': user.nickname, 'role': user.role}, csrf_token=generate_csrf())


@api.post('/auth/logout')
@require_roles()
def logout():
    end_session()
    return '', 204


@api.get('/games')
def list_games():
    if 'after' in request.args:
        if 'page' in request.args:
            raise ValidationError('Use page ou after, nunca ambos.')
        items, cursor = games().cursor(request.args['after'], request.args.get('per_page', 20))
        return jsonify(data=[asdict(item) for item in items], meta={'next_cursor': cursor},
                       links={'next': url_for('api.list_games', after=cursor, per_page=request.args.get('per_page', 20)) if cursor is not None else None})
    items, meta = games().list(request.args.get('page', 1), request.args.get('per_page', 20))
    page, size = meta['page'], meta['per_page']
    links = {'next': url_for('api.list_games', page=page + 1, per_page=size) if page < meta['pages'] else None,
             'previous': url_for('api.list_games', page=page - 1, per_page=size) if page > 1 else None}
    return jsonify(data=[asdict(item) for item in items], meta=meta, links=links)


@api.get('/games/<int:game_id>')
def get_game(game_id):
    return jsonify(data=asdict(games().get(game_id)))


@api.post('/games')
@require_roles('editor', 'admin')
def create_game():
    key = request.headers.get('Idempotency-Key')
    if key is not None and not re.fullmatch(r'[A-Za-z0-9_-]{8,128}', key):
        raise ValidationError('Idempotency-Key: use 8–128 letras, números, _ ou -.')
    game = games().create(payload(), idempotency_key=key)
    return jsonify(data=asdict(game)), 201, {'Location': url_for('api.get_game', game_id=game.id)}


@api.put('/games/<int:game_id>')
@require_roles('editor', 'admin')
def update_game(game_id):
    return jsonify(data=asdict(games().update(game_id, payload())))


@api.delete('/games/<int:game_id>')
@require_roles('admin')
def delete_game(game_id):
    games().delete(game_id)
    return '', 204


@web.get('/')
def index():
    items, meta = games().list(request.args.get('page', 1), request.args.get('per_page', 20))
    return render_template('lista.html', titulo='Jogos', jogos=items, meta=meta)


@web.get('/login')
def login_page():
    return render_template('login.html', titulo='Login', form=LoginForm())


@web.post('/autenticar')
def autenticar():
    form = LoginForm()
    if not form.validate_on_submit():
        raise ValidationError('Informe nickname e senha válidos.')
    sign_in(form.nickname.data, form.senha.data, form.otp.data)
    return redirect(url_for('web.index'), code=303)


@web.post('/logout')
@require_roles()
def logout_page():
    end_session()
    return redirect(url_for('web.index'), code=303)


@web.get('/novo')
@require_roles('editor', 'admin')
def novo():
    return render_template('novo.html', titulo='Novo jogo', form=GameForm())


@web.get('/editar/<int:id>')
@require_roles('editor', 'admin')
def editar(id):
    game = games().get(id)
    return render_template('editar.html', titulo='Editar jogo', id=id,
                           form=GameForm(data=asdict(game)))


def form_fields():
    form = GameForm()
    if not form.validate_on_submit():
        raise ValidationError('Verifique os campos: ' + ', '.join(form.errors))
    return {key: getattr(form, key).data for key in ('nome', 'categoria', 'console')}


@web.post('/criar')
@require_roles('editor', 'admin')
def criar():
    fields = form_fields()
    cover = read_cover(request.files.get('arquivo'))
    games().create(fields, cover=cover)
    return redirect(url_for('web.index'), code=303)


@web.post('/atualizar')
@require_roles('editor', 'admin')
def atualizar():
    fields = form_fields()
    try:
        game_id = int(request.form.get('id', ''))
    except ValueError:
        raise BadRequest('ID inválido.') from None
    cover = read_cover(request.files.get('arquivo'))
    games().update(game_id, fields, cover=cover)
    return redirect(url_for('web.index'), code=303)


@web.post('/deletar/<int:id>')
@require_roles('admin')
def deletar(id):
    games().delete(id)
    return redirect(url_for('web.index'), code=303)


@web.get('/uploads/<nome_arquivo>')
def imagem(nome_arquivo):
    if nome_arquivo != 'capa_padrao.jpg':
        raise NotFound('Imagem não encontrada.')
    return send_file(current_app.config['DEFAULT_COVER'], max_age=3600)


@api.get('/auth/me')
@require_roles()
def me():
    user = current_user()
    return jsonify(data={'nickname': user.nickname, 'role': user.role})


@api.get('/games/<int:game_id>/cover')
def game_cover(game_id):
    games().get(game_id)
    cover = db.session.get(CoverModel, game_id)
    if not cover:
        return send_file(current_app.config['DEFAULT_COVER'], max_age=60)
    # Allow revalidation without loading the deferred BLOB on a 304 response.
    if request.if_none_match.contains(cover.digest):
        response = current_app.response_class(status=304)
        response.set_etag(cover.digest)
        response.cache_control.public = True
        response.cache_control.max_age = 60
        return response
    return send_file(BytesIO(cover.content), mimetype='image/jpeg', etag=cover.digest, max_age=60)


def register_errors(app):
    @app.after_request
    def secure_headers(response):
        response.headers['X-Request-ID'] = getattr(g, 'request_id', uuid4().hex)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if app.config['SESSION_COOKIE_SECURE']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if request.endpoint not in {'api.game_cover', 'web.imagem', 'static'} or response.status_code >= 400:
            response.headers['Cache-Control'] = 'no-store'
        return response

    def error_response(status, message, original=None):
        request_id = getattr(g, 'request_id', uuid4().hex)
        if request.path.startswith('/api/'):
            response = jsonify(error={'status': status, 'message': message, 'request_id': request_id})
        else:
            response = app.make_response(render_template('erro.html', titulo=f'Erro {status}', message=message))
        response.status_code = status
        if original:
            for name, value in original.get_headers():
                if name.lower() not in ('content-type', 'content-length'):
                    response.headers[name] = value
        return response

    @app.errorhandler(DomainError)
    def domain_error(error):
        db.session.rollback()
        status = {ValidationError: 422, NotFound: 404, Conflict: 409, Unauthorized: 401, Forbidden: 403, QuotaExceeded: 409}[type(error)]
        return error_response(status, str(error))

    @app.errorhandler(HTTPException)
    def http_error(error):
        return error_response(error.code, error.description, error)

    @app.errorhandler(RedisError)
    @app.errorhandler(OperationalError)
    @app.errorhandler(DatabaseTimeout)
    def unavailable(error):
        db.session.rollback()
        app.logger.error('dependency_unavailable type=%s request_id=%s', type(error).__name__, getattr(g, 'request_id', None))
        response = error_response(503, 'Serviço temporariamente indisponível.')
        response.headers['Retry-After'] = '5'
        return response

    @app.errorhandler(Exception)
    def unexpected_error(error):
        db.session.rollback()
        app.logger.exception('Falha interna request_id=%s', getattr(g, 'request_id', 'unknown'))
        return error_response(500, 'Erro interno. Informe o identificador da requisição ao suporte.')
