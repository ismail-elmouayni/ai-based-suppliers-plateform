#!/bin/bash
set -e

echo "==> Starting Superset initialisation..."
/app/init_superset.sh

echo "==> Starting Superset server (gunicorn)..."
exec gunicorn \
    --bind "0.0.0.0:8088" \
    --access-logfile "-" \
    --error-logfile "-" \
    --workers 1 \
    --worker-class gthread \
    --threads 20 \
    --timeout 120 \
    --limit-request-line 0 \
    --limit-request-field_size 0 \
    "superset.app:create_app()"
