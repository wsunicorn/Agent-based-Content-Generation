#!/usr/bin/env bash
set -o errexit

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"
export CELERY_LOG_LEVEL="${CELERY_LOG_LEVEL:-info}"
export CELERY_WORKER_POOL="${CELERY_WORKER_POOL:-solo}"
export CELERY_WORKER_CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-1}"

exec celery -A config worker \
  -l "$CELERY_LOG_LEVEL" \
  -P "$CELERY_WORKER_POOL" \
  --concurrency="$CELERY_WORKER_CONCURRENCY"
