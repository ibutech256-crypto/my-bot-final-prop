#!/usr/bin/env sh
set -eu
cd backend
python manage.py check
pytest -q
