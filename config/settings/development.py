"""Development settings."""
from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# ---------------------------------------------------------------------------
# Debug toolbar
# ---------------------------------------------------------------------------
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa: F405
INTERNAL_IPS = ["127.0.0.1"]

# ---------------------------------------------------------------------------
# Email (console backend for dev)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# DRF — open permissions for dev (no login required)
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
}

# ---------------------------------------------------------------------------
# Relaxed security for dev
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Celery — Windows-compatible settings
# ---------------------------------------------------------------------------
CELERY_TASK_SOFT_TIME_LIMIT = None   # Disable soft timeout (SIGUSR1 not on Windows)
CELERY_WORKER_POOL = "solo"          # solo pool avoids prefork issues on Windows
