"""
Django settings for the Kararsizim project.

All secrets and environment-specific values come from environment variables.
Locally they are read from a `.env` file in the project root (see .env.example).
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name):
    value = os.environ.get(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


# --- Core ---------------------------------------------------------------

DEBUG = env_bool("DEBUG", default=False)

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key-do-not-use-in-production"
    else:
        raise ImproperlyConfigured("SECRET_KEY environment variable is required when DEBUG is off.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Vercel exposes the deployment and production hostnames as env vars;
# trust them automatically so preview and production deploys both work.
for var in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
    host = os.environ.get(var)
    if host:
        ALLOWED_HOSTS.append(host)
        CSRF_TRUSTED_ORIGINS.append(f"https://{host}")

# Vercel can also serve the project under extra *.vercel.app aliases (for example
# a generated production domain) that these variables do not list. Vercel routes
# requests by hostname, so only this project's own domains ever reach the app.
if not DEBUG:
    ALLOWED_HOSTS.append(".vercel.app")
    CSRF_TRUSTED_ORIGINS.append("https://*.vercel.app")

if DEBUG:
    ALLOWED_HOSTS += ["localhost", "127.0.0.1", "[::1]"]


# --- Applications -------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "polls",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Database (Supabase Postgres via the transaction pooler) -------------
# SQLite is intentionally not supported: Vercel's filesystem is not persistent.

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL environment variable is required (see .env.example).")

_db = dj_database_url.parse(DATABASE_URL, conn_max_age=0)
_db_options = _db.setdefault("OPTIONS", {})
if "postgresql" in _db["ENGINE"]:
    # The transaction pooler (Supavisor, port 6543) does not support server-side
    # prepared statements, so psycopg's automatic preparation must be disabled.
    _db_options["prepare_threshold"] = None
    if _db.get("HOST") not in {"localhost", "127.0.0.1", ""}:
        _db_options.setdefault("sslmode", "require")
# Server-side cursors break under transaction pooling.
_db["DISABLE_SERVER_SIDE_CURSORS"] = True

DATABASES = {"default": _db}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Auth ---------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/giris/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Sessions are stored in the database (Django's default backend).
SESSION_ENGINE = "django.contrib.sessions.backends.db"


# --- Internationalization -----------------------------------------------

LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True


# --- Static files -------------------------------------------------------
# Vercel runs collectstatic automatically when STATIC_ROOT is set and serves
# the result from its CDN; WhiteNoise covers local and non-CDN serving.

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}


# --- Security (production) ----------------------------------------------

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))
