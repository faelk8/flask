from io import BytesIO
import pytest
from app.infrastructure import db, GameModel

GAME = {'nome': 'Tetris', 'categoria': 'Puzzle', 'console': 'PC'}


def test_crud_and_pagination(logged):
    client, headers = logged
    created = client.post('/api/v1/games', json=GAME, headers=headers)
    assert created.status_code == 201
    location = created.headers['Location']
    assert client.get(location).json['data']['nome'] == 'Tetris'
    assert client.post('/api/v1/games', json=GAME, headers=headers).status_code == 409
    client.post('/api/v1/games', json={**GAME, 'nome': 'Doom'}, headers=headers)
    page = client.get('/api/v1/games?page=2&per_page=1').json
    assert page['meta'] == {'page': 2, 'per_page': 1, 'total': 2, 'pages': 2}
    assert page['data'][0]['nome'] == 'Doom'
    assert page['links']['previous'] and page['links']['next'] is None
    assert client.put(location, json={**GAME, 'nome': 'Quake'}, headers=headers).status_code == 200
    deleted = client.delete(location, headers=headers)
    assert deleted.status_code == 204 and deleted.data == b''
    assert client.get(location).status_code == 404


@pytest.mark.parametrize('query', ['page=0', 'page=no', 'per_page=101', 'per_page=-1', 'page=100001'])
def test_bad_pagination(client, query):
    assert client.get('/api/v1/games?' + query).status_code == 422


def test_auth_csrf_and_safe_methods(client):
    assert client.post('/api/v1/games', json=GAME).status_code == 400
    token = client.get('/api/v1/csrf').json['csrf_token']
    headers = {'X-CSRFToken': token}
    assert client.post('/api/v1/games', json=GAME, headers=headers).status_code == 401
    assert client.post('/criar', data=GAME, headers=headers).status_code == 401
    assert client.post('/atualizar', data=GAME, headers=headers).status_code == 401
    assert client.get('/deletar/1').status_code == 405
    assert client.get('/logout').status_code == 405
    response = client.post('/api/v1/auth/login', json={'nickname': 'missing', 'senha': 'wrong'}, headers=headers)
    assert response.status_code == 401
    assert 'senha' not in response.json['error']['message']


@pytest.mark.parametrize('data', [[], {}, {**GAME, 'nome': ' '}, {**GAME, 'nome': 'a' * 51}, {**GAME, 'id': 1}])
def test_invalid_body(logged, data):
    client, headers = logged
    assert client.post('/api/v1/games', json=data, headers=headers).status_code == 422


def test_http_errors_and_headers(logged):
    client, headers = logged
    assert client.post('/api/v1/games', data='{', content_type='application/json', headers=headers).status_code == 400
    assert client.post('/api/v1/games', data='text', headers=headers).status_code == 415
    response = client.patch('/api/v1/games/1', json=GAME, headers=headers)
    assert response.status_code == 405
    assert 'GET' in response.headers['Allow']
    assert response.json['error']['request_id']
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert client.get('/api/v1/missing').status_code == 404


def test_internal_error_is_private(app, client):
    class BrokenService:
        def list(self, *args):
            raise RuntimeError('secret-database-password')
    app.extensions['games'] = BrokenService()
    response = client.get('/api/v1/games')
    assert response.status_code == 500
    assert b'secret-database-password' not in response.data


def test_web_flow_and_upload_validation(logged):
    client, headers = logged
    assert client.get('/').status_code == 200
    assert client.get('/login').status_code == 200
    assert client.get('/novo').status_code == 200
    response = client.post('/criar', data={**GAME, 'arquivo': (BytesIO(b'fake image'), 'fake.jpg')}, headers=headers)
    assert response.status_code == 422
    assert client.get('/api/v1/games').json['meta']['total'] == 0
    assert client.post('/criar', data=GAME, headers=headers).status_code == 303
    assert client.get('/editar/1').status_code == 200
    assert client.post('/atualizar', data={**GAME, 'id': '1'}, headers=headers).status_code == 303
    assert client.post('/deletar/1', headers=headers).status_code == 303


def test_logout_clears_auth(logged):
    client, headers = logged
    assert client.post('/api/v1/auth/logout', headers=headers).status_code == 204
    token = client.get('/api/v1/csrf').json['csrf_token']
    assert client.delete('/api/v1/games/1', headers={'X-CSRFToken': token}).status_code == 401


def test_upload_size_limit(logged):
    client, headers = logged
    response = client.post('/criar', data={**GAME, 'arquivo': (BytesIO(b'x' * (2 * 1024 * 1024)), 'large.jpg')}, headers=headers)
    assert response.status_code == 413


def test_no_open_redirect(logged):
    client, headers = logged
    result = client.post('/autenticar', data={'nickname': 'admin', 'senha': 'strong-password', 'proxima': 'https://evil.example'}, headers=headers)
    assert result.status_code == 303
    assert result.headers['Location'] == '/'


def test_init_db_preserves_data(app):
    with app.app_context():
        db.session.add(GameModel(**GAME))
        db.session.commit()
    result = app.test_cli_runner().invoke(args=['init-db'])
    assert result.exit_code == 0
    with app.app_context():
        assert db.session.query(GameModel).count() == 1


def test_rate_limit(tmp_path):
    from app import create_app
    application = create_app({'TESTING': True, 'SECRET_KEY': 'test-key-' * 5,
                              'SQLALCHEMY_DATABASE_URI': 'sqlite://',
                              'RATELIMIT_ENABLED': True})
    with application.app_context():
        db.create_all()
    client = application.test_client()
    token = client.get('/api/v1/csrf').json['csrf_token']
    for _ in range(5):
        assert client.post('/api/v1/auth/login', json={'nickname': 'unknown', 'senha': 'wrong'}, headers={'X-CSRFToken': token}).status_code == 401
    result = client.post('/api/v1/auth/login', json={}, headers={'X-CSRFToken': token})
    assert result.status_code == 429
    assert 'Retry-After' in result.headers


def test_valid_cover(logged, app):
    from PIL import Image
    client, headers = logged
    stream = BytesIO()
    Image.new('RGB', (4, 4)).save(stream, 'JPEG')
    stream.seek(0)
    result = client.post('/criar', data={**GAME, 'arquivo': (stream, '../../image.jpg')}, headers=headers)
    assert result.status_code == 303
    assert client.get('/api/v1/games/1/cover').status_code == 200
    client.delete('/api/v1/games/1', headers=headers)
    assert client.get('/api/v1/games/1/cover').status_code == 404
