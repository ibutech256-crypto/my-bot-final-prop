#!/usr/bin/env sh
set -eu
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn backend.config.asgi:application -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --workers ${WEB_CONCURRENCY:-3} --timeout 120
