import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# -------------------------
# Base directory
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv(BASE_DIR / ".env")

# -------------------------
# Core settings
# -------------------------
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

DEBUG = os.getenv("DEBUG", "false").lower() == "true"


ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "ai-chatbox1-4ecb.onrender.com",
    "ai-chatbox-6sey.onrender.com",
]

# -------------------------
# Applications
# -------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "corsheaders",

    # Cloudinary apps (safe even in local)
    "cloudinary",
    "cloudinary_storage",

    "chat",
    "accounts",
    "payments",
    "anymail"
]

CORS_ALLOW_CREDENTIALS = True

# -------------------------
# Middleware
# -------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
# -------------------------
# URLs / WSGI
# -------------------------
ROOT_URLCONF = "backend.urls"
WSGI_APPLICATION = "backend.wsgi.application"

# -------------------------
# Templates
# -------------------------
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

# -------------------------
# Database (SQLite for now)
# -------------------------
if os.getenv("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.parse(
            os.getenv("DATABASE_URL"),
            conn_max_age=600,
            ssl_require=not DEBUG,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# -------------------------
# Localization
# -------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# -------------------------
# Static files
# -------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# -------------------------
# Media / Storage
# -------------------------
USE_CLOUDINARY = bool(os.getenv("CLOUDINARY_URL"))



if USE_CLOUDINARY:
    # ✅ Production (Cloudinary)
    DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"
    CLOUDINARY_STORAGE = {
        
        "MEDIA_FOLDER": "uploads",
    }
else:
    DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"



# -------------------------
# Cache backend
# -------------------------
# DatabaseCache works with both SQLite (local) and PostgreSQL (production)
# without any extra services. Shared across all workers — rate limiting and
# login lockouts are global, not per-process.
# Run once after deploy: python manage.py createcachetable
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache_table",
    }
}

# -------------------------
# Default primary key
# -------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------
# Session lifetime
# -------------------------
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 1 week

# -------------------------
# Django REST Framework
# -------------------------


# -------------------------
# CORS / CSRF
# -------------------------
CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://ai-chatbox1-4ecb.onrender.com",
    "https://ai-chatbox-6sey.onrender.com",
]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://ai-chatbox1-4ecb.onrender.com",
    "https://ai-chatbox-6sey.onrender.com",
]

from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + ["Idempotency-Key", "X-CSRFToken", "X-Razorpay-Signature"]

# -------------------------
# Logging
# -------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Per-user throttle scopes for LLM endpoints (uses Django cache backend).
    # Limits are per authenticated user, not per IP.
    "DEFAULT_THROTTLE_CLASSES": [],  # no global throttle — applied per-view only
    "DEFAULT_THROTTLE_RATES": {
        "llm_chat":  "60/hour",   # regular / uncensored chat
        "llm_ocr":   "30/hour",   # OCR Q&A and image analysis
        "llm_debug": "20/hour",   # multi-debugger (most expensive)
    },
}
EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"

ANYMAIL = {
    "BREVO_API_KEY": os.getenv("BREVO_API_KEY"),
}

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "eclipsexautomationsolution@gmail.com")

# -------------------------
# Razorpay
# -------------------------
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")




SESSION_COOKIE_HTTPONLY  = True
CSRF_COOKIE_HTTPONLY     = False
SESSION_COOKIE_AGE       = 60 * 60 * 24 * 7   # 1 week (was Django default 2 weeks)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False         # keep session across browser restarts
# 🔐 Auth + Sessions
if DEBUG:
    # ✅ Local development
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SECURE = False
else:
    # ✅ Production (Render / HTTPS)
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SECURE = True
    

# 🔑 CORS
CORS_ALLOW_CREDENTIALS = True

if not DEBUG:
    SECURE_PROXY_SSL_HEADER        = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS            = 31536000  # 1 year — browsers enforce HTTPS-only
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD            = True
    SECURE_SSL_REDIRECT            = True      # redirect plain HTTP → HTTPS
