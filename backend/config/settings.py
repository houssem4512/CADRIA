"""
Django settings for Cadria — Copilote IA de cadrage, découpage & pilotage de projets.
"""
import os
from datetime import timedelta
from pathlib import Path

# Load .env file from backend/ directory (next to manage.py)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # python-dotenv not installed — env vars must be set manually

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-cadria-dev-key-change-me-in-production-9f3a2b",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = ["*"]

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "corsheaders",
    # Local
    "accounts",
    "projects",
    "orchestration",
    "notifications",
    "analytics",
    "audit",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database — SQLite by default (swap via DATABASE_URL for Postgres in prod)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# CORS — the React dev server talks to this API
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = False
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

# ---------------------------------------------------------------------------
# Django REST Framework + JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": (
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# Agents are plugged in later — these toggles drive the "reserved slot" UI.
AGENT_RUNTIME = {
    "ENABLED": os.environ.get("AGENT_RUNTIME_ENABLED", "False") == "True",
    "SCOPING_ENDPOINT": os.environ.get("SCOPING_AGENT_URL", ""),
    "OPS_ENDPOINT": os.environ.get("OPS_AGENT_URL", ""),
    "RISK_ENDPOINT": os.environ.get("RISK_AGENT_URL", ""),
    "ORCHESTRATOR": os.environ.get("ORCHESTRATOR", "LangGraph"),
}

# ---------------------------------------------------------------------------
# LLM configuration (Agent 1 — Scoping)
# Uses Groq Cloud (free, no local hardware) by default.
# Get a free key at https://console.groq.com
# ---------------------------------------------------------------------------
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq")  # groq | fallback
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TIMEOUT = int(os.environ.get("GROQ_TIMEOUT", "60"))
GROQ_MAX_TOKENS = int(os.environ.get("GROQ_MAX_TOKENS", "8000"))

# ---------------------------------------------------------------------------
# Trello OAuth — app-level API key (one-time setup)
# Get it at https://trello.com/power-ups/admin
# Each user connects their own Trello account via /api/trello/auth-url/
# ---------------------------------------------------------------------------
TRELLO_APP_KEY = os.environ.get("TRELLO_APP_KEY", "")

# ---------------------------------------------------------------------------
# Celery — for Agent 3 (Risk) weekly scheduling
# Uses Django DB broker (simplest — no Redis needed for dev).
# For production, switch to Redis: CELERY_BROKER_URL = "redis://localhost:6379/0"
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = "django-db"
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE = {
    "risk-agent-weekly": {
        "task": "cadria.run_risk_agent_all_projects",
        "schedule": 604800.0,  # 7 days in seconds (weekly)
    },
    "risk-model-retrain-monthly": {
        "task": "cadria.train_risk_model_monthly",
        "schedule": 2592000.0,  # 30 days in seconds (monthly)
    },
}
