"""Health, structured request logs and bounded-cardinality Prometheus metrics."""
import hmac
import json
import logging
import os
import time
from uuid import uuid4
from flask import Blueprint, Response, current_app, g, request
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest, multiprocess
from redis import Redis
from sqlalchemy import text
from .infrastructure import db

ops = Blueprint('ops', __name__)
REGISTRY = CollectorRegistry()
REQUESTS = Counter('jogoteca_http_requests', 'HTTP responses', ['endpoint', 'method', 'status'], registry=REGISTRY)
DURATION = Histogram('jogoteca_http_duration_seconds', 'HTTP duration', ['endpoint', 'method'],
                     buckets=(.01, .05, .1, .25, .5, 1, 2, 5, 10, 30), registry=REGISTRY)


def install_observability(app):
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def begin_request():
        g.request_id = uuid4().hex
        g.started_at = time.monotonic()

    @app.after_request
    def observe(response):
        elapsed = time.monotonic() - getattr(g, 'started_at', time.monotonic())
        endpoint = request.endpoint or 'unmatched'
        method = request.method if request.method in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'} else 'OTHER'
        if endpoint not in {'ops.metrics', 'ops.live', 'ops.ready', 'static'}:
            REQUESTS.labels(endpoint, method, str(response.status_code)).inc()
            DURATION.labels(endpoint, method).observe(elapsed)
            app.logger.info(json.dumps({'event': 'http_request', 'request_id': getattr(g, 'request_id', None),
                'endpoint': endpoint, 'method': method, 'status': response.status_code,
                'duration_ms': round(elapsed * 1000, 2)}))
        return response

    if app.config['RATELIMIT_STORAGE_URI'].startswith(('redis://', 'rediss://')):
        app.extensions['redis_health'] = Redis.from_url(app.config['RATELIMIT_STORAGE_URI'], socket_timeout=2, socket_connect_timeout=2)


@ops.get('/health/live')
def live():
    return {'status': 'alive'}


@ops.get('/health/ready')
def ready():
    try:
        db.session.execute(text('SELECT 1'))
        # Catch a missing or outdated migration as well as an unreachable database.
        db.session.execute(text('SELECT role, active FROM usuarios LIMIT 1'))
        db.session.execute(text('SELECT used_bytes FROM storage_quota WHERE id = 1')).scalar_one()
        db.session.rollback()
        redis = current_app.extensions.get('redis_health')
        if redis:
            redis.ping()
        return {'status': 'ready'}
    except Exception:
        db.session.rollback()
        current_app.logger.error('readiness_failed request_id=%s', getattr(g, 'request_id', None))
        return {'status': 'unavailable'}, 503, {'Retry-After': '5'}


@ops.get('/internal/metrics')
def metrics():
    expected = current_app.config['METRICS_TOKEN']
    supplied = request.headers.get('Authorization', '')
    if not expected or not hmac.compare_digest(supplied, 'Bearer ' + expected):
        return {'error': 'not found'}, 404
    registry = REGISTRY
    if os.environ.get('PROMETHEUS_MULTIPROC_DIR'):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    return Response(generate_latest(registry), content_type='text/plain; version=0.0.4; charset=utf-8')
