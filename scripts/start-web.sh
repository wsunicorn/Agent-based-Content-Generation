#!/usr/bin/env bash
set -o errexit

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"
export PORT="${PORT:-8000}"

python manage.py migrate --no-input
python manage.py collectstatic --no-input

exec daphne -b 0.0.0.0 -p "$PORT" config.asgi:application
