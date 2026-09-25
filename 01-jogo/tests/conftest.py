import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.infrastructure import db, UserModel, BcryptHasher, StorageQuota


@pytest.fixture
def app(tmp_path):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret-' * 4,
                      'SQLALCHEMY_DATABASE_URI': 'sqlite://',
                      'UPLOAD_PATH': str(tmp_path), 'RATELIMIT_ENABLED': False})
    with app.app_context():
        db.create_all()
        db.session.add(StorageQuota(id=1, used_bytes=0))
        db.session.add(UserModel(role='admin', nickname='admin', nome='Admin', senha=BcryptHasher().hash('strong-password')))
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def logged(client):
    token = client.get('/api/v1/csrf').json['csrf_token']
    response = client.post('/api/v1/auth/login', json={'nickname': 'admin', 'senha': 'strong-password'}, headers={'X-CSRFToken': token})
    assert response.status_code == 200
    return client, {'X-CSRFToken': response.json['csrf_token']}
