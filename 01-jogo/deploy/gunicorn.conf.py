"""Bounded resources; tune using measured workload and database connection limits."""
import os
from prometheus_client import multiprocess

bind = '0.0.0.0:8000'
workers = int(os.getenv('WEB_WORKERS', '2'))
worker_class = 'gthread'
threads = int(os.getenv('WEB_THREADS', '2'))
timeout = 30
graceful_timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
limit_request_line = 4094
limit_request_fields = 50
limit_request_field_size = 8190
worker_tmp_dir = '/tmp'
# ProxyFix handles forwarding explicitly. Gunicorn must not trust arbitrary headers.
forwarded_allow_ips = ''
accesslog = None  # Application emits structured logs without URLs, cookies or bodies.
errorlog = '-'
preload_app = False


def child_exit(server, worker):
    multiprocess.mark_process_dead(worker.pid)
