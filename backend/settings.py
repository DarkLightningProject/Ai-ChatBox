"""
Django settings for backend project (DEV quick-start).
Django 5.2.x
"""

from pathlib import Path
import os

# Load .env properly
from dotenv import load_dotenv
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent

# 🔥 Correct path to your .env file:
env_path = os.path.join(BASE_DIR, "..", ".env")

# Core
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-only-secret-key-change-me",
)

DEBUG = True

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# ------------------------------------------------------------
# Apps
# ------------------------------------------------------------
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "corsheaders",

    # Local
    "chat",
]

# ------------------------------------------------------------
# Middleware (CORS BEFORE CommonMiddleware)
# ------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    "corsheaders.middleware.CorsMiddleware",      # <— keep this high
    "django.middleware.common.CommonMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

# ------------------------------------------------------------
# Templates
# ------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"

# ------------------------------------------------------------
# Database (SQLite for dev)
# ------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ------------------------------------------------------------
# Password validation
# ------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------
# I18N
# ------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------
# Static & Media
# ------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------
# DRF (open for dev)
# ------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
}

# ------------------------------------------------------------
# CORS / CSRF (DEV: allow all)
# ------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True              # <— DEV-ONLY
CORS_ALLOW_CREDENTIALS = False             # keep False unless using cookies

from corsheaders.defaults import default_headers, default_methods
CORS_ALLOW_HEADERS = list(default_headers) + ["content-type", "authorization"]
CORS_ALLOW_METHODS = list(set(list(default_methods) + ["GET", "POST", "OPTIONS", "PATCH", "DELETE"]))

# If you later switch to credentials/cookies, set:
# CORS_ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"]
# CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
# CORS_ALLOW_ALL_ORIGINS = False
# CORS_ALLOW_CREDENTIALS = True

# ------------------------------------------------------------
# Logging (handy for debugging requests)
# ------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "[{levelname}] {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# ------------------------------------------------------------
# Optional: expose keys to your views (they already read from env)
# ------------------------------------------------------------
# 




BASE_DIR = Path(__file__).resolve().parent.parent

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + [
    "Idempotency-Key",           # <— allow your custom header
]
