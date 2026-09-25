#!/bin/sh
set -eu
# Directory is private to this container. Clean only at master startup, never per worker.
export PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
rm -f "$PROMETHEUS_MULTIPROC_DIR"/*.db
exec gunicorn --config /srv/gunicorn.conf.py 'app:create_app()'
