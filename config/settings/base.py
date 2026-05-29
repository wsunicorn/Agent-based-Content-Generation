"""
Django base settings for content_pipeline project.
"""
from pathlib import Path
import environ

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Read environment variables from .env file
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")


def _parse_env_mapping(value: str) -> dict[str, str]:
    """Parse comma-separated key=value or key:value mappings from env vars."""
    mapping: dict[str, str] = {}
    for item in (value or "").split(","):
        item = item.strip()
        if not item:
            continue
        separator = "=" if "=" in item else ":"
        if separator not in item:
            continue
        key, raw_value = item.split(separator, 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if key and raw_value:
            mapping[key] = raw_value
    return mapping


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "channels",
    "django_celery_results",
]

LOCAL_APPS = [
    "apps.jobs",
    "apps.agents",
    "apps.pipeline",
    "apps.dashboard",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ---------------------------------------------------------------------------
# URLs & WSGI/ASGI
# ---------------------------------------------------------------------------
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3")
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & Media files
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# ---------------------------------------------------------------------------
# Django Channels (WebSocket)
# ---------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("REDIS_URL", default="redis://localhost:6379/0")],
        },
    },
}
if env.bool("USE_INMEMORY_CHANNEL_LAYER", default=False):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = env.bool("CELERY_TASK_EAGER_PROPAGATES", default=True)
CELERY_TASK_TIME_LIMIT = 3600  # 1 hour hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 3300  # warn at 55 minutes

LOGIN_URL = "/admin/login/"

# ---------------------------------------------------------------------------
# LLM providers
# ---------------------------------------------------------------------------
LLM_MODE = env("LLM_MODE", default="balanced").lower()  # cheap | balanced | quality
LLM_PROVIDER = env("LLM_PROVIDER", default="gemini").lower()
LOCAL_LLM_PROVIDER = env("LOCAL_LLM_PROVIDER", default="ollama").lower()
STRUCTURED_LLM_PROVIDER = env("STRUCTURED_LLM_PROVIDER", default="gemini").lower()
LOCAL_LLM_AGENTS = env.list("LOCAL_LLM_AGENTS", default=["writer", "editor", "qa"])
LLM_AGENT_PROVIDERS = _parse_env_mapping(env("LLM_AGENT_PROVIDERS", default=""))
LLM_AGENT_MODELS = _parse_env_mapping(env("LLM_AGENT_MODELS", default=""))
GEMINI_AGENT_MODELS = _parse_env_mapping(env("GEMINI_AGENT_MODELS", default=""))
LLM_FALLBACK_TO_GEMINI = env.bool("LLM_FALLBACK_TO_GEMINI", default=True)
LOCAL_LLM_REQUEST_DELAY = env.float("LOCAL_LLM_REQUEST_DELAY", default=0.0)
LOCAL_LLM_TIMEOUT = env.int("LOCAL_LLM_TIMEOUT", default=180)

# ---------------------------------------------------------------------------
# Google Gemini (free-tier: 10 RPM, 250 RPD)
# ---------------------------------------------------------------------------
GOOGLE_API_KEY = env("GOOGLE_API_KEY", default="")
GEMINI_MODEL = env("GEMINI_MODEL", default="gemini-3.1-flash-lite")
GEMINI_REQUEST_DELAY = env.float("GEMINI_REQUEST_DELAY", default=6.5)  # seconds between calls
GEMINI_DAILY_LIMIT = env.int("GEMINI_DAILY_LIMIT", default=250)
GEMINI_DAILY_WARN_AT = env.int("GEMINI_DAILY_WARN_AT", default=200)

# ---------------------------------------------------------------------------
# Local / OpenAI-compatible LLMs
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", default="http://localhost:11434")
OLLAMA_MODEL = env("OLLAMA_MODEL", default="qwen2.5:7b")
OLLAMA_THINK = env.bool("OLLAMA_THINK", default=False)
OLLAMA_FAST_MODEL = env("OLLAMA_FAST_MODEL", default="qwen2.5:3b")
OLLAMA_REASONING_MODEL = env("OLLAMA_REASONING_MODEL", default="qwen3:8b")
OLLAMA_STRUCTURED_MODEL = env("OLLAMA_STRUCTURED_MODEL", default="qwen2.5:7b")
OLLAMA_EMBED_MODEL = env("OLLAMA_EMBED_MODEL", default="nomic-embed-text-v2-moe")
OLLAMA_REQUIRED_MODELS = env.list(
    "OLLAMA_REQUIRED_MODELS",
    default=[
        "qwen2.5:7b",
        "qwen3:8b",
        "nomic-embed-text-v2-moe",
    ],
)
MAX_PARALLEL_WRITERS = env.int("MAX_PARALLEL_WRITERS", default=2)
PIPELINE_QUALITY_MODE = env("PIPELINE_QUALITY_MODE", default="standard").lower()
MAX_PIPELINE_REVISIONS = env.int("MAX_PIPELINE_REVISIONS", default=2)
MAX_AGENT_RETRIES = env.int("MAX_AGENT_RETRIES", default=1)
LANGGRAPH_RECURSION_LIMIT = env.int("LANGGRAPH_RECURSION_LIMIT", default=80)
FACT_CHECK_MODE = env("FACT_CHECK_MODE", default="adaptive").lower()
FACT_CHECK_MAX_CLAIMS = env.int("FACT_CHECK_MAX_CLAIMS", default=6)
FACT_CHECK_SKIP_SOFT_CONTENT = env.bool("FACT_CHECK_SKIP_SOFT_CONTENT", default=True)
FAST_MODE_WEB_SEARCH = env.bool("FAST_MODE_WEB_SEARCH", default=True)
FAST_MODE_LLM_QA = env.bool("FAST_MODE_LLM_QA", default=True)
FAST_MODE_LLM_SEO = env.bool("FAST_MODE_LLM_SEO", default=True)
RESEARCH_MAX_SOURCES = env.int("RESEARCH_MAX_SOURCES", default=4)
RESEARCH_CACHE_TTL = env.int("RESEARCH_CACHE_TTL", default=86400)
SCRAPE_CACHE_TTL = env.int("SCRAPE_CACHE_TTL", default=604800)
IMAGE_SEARCH_ENABLED = env.bool("IMAGE_SEARCH_ENABLED", default=True)
IMAGE_SEARCH_PROVIDER = env("IMAGE_SEARCH_PROVIDER", default="wikimedia_commons").lower()
IMAGE_SEARCH_MAX_RESULTS = env.int("IMAGE_SEARCH_MAX_RESULTS", default=2)
IMAGE_SEARCH_USER_AGENT = env(
    "IMAGE_SEARCH_USER_AGENT",
    default="DomainLLMAssistant/1.0 (local development)",
)
OPENAI_COMPATIBLE_BASE_URL = env(
    "OPENAI_COMPATIBLE_BASE_URL",
    default="http://localhost:1234/v1",
)
OPENAI_COMPATIBLE_MODEL = env("OPENAI_COMPATIBLE_MODEL", default="local-model")
OPENAI_COMPATIBLE_API_KEY = env("OPENAI_COMPATIBLE_API_KEY", default="")

# ---------------------------------------------------------------------------
# Tavily Search API
# ---------------------------------------------------------------------------
ENABLE_WEB_SEARCH = env.bool("ENABLE_WEB_SEARCH", default=True)
TAVILY_API_KEY = env("TAVILY_API_KEY", default="")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
