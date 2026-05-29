"""Celery application for content_pipeline project."""
# Gevent monkey patching for cooperative networking on Windows
import sys
if "gevent" in sys.argv:
    try:
        from gevent import monkey
        monkey.patch_all()
    except ImportError:
        pass

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
app = Celery("content_pipeline")

# Use Django settings for Celery configuration (namespace CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Fix deprecation warning for Celery 6.0
app.conf.broker_connection_retry_on_startup = True

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
