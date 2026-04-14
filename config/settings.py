import os
from urllib.parse import urlparse
from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import AutoConfig, Csv, Config, RepositoryEnv, UndefinedValueError


def cast_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on", "debug"}


def normalize_host(value):
    candidate = str(value).strip()
    if not candidate:
        return ""
    if "://" in candidate:
        parsed = urlparse(candidate)
        candidate = parsed.netloc or parsed.path
    candidate = candidate.split("/")[0].strip()
    return candidate


def normalize_hosts(values):
    normalized = []
    for value in values:
        host = normalize_host(value)
        if host and host not in normalized:
            normalized.append(host)
    return normalized

BASE_DIR = Path(__file__).resolve().parent.parent

env_file = os.environ.get("ENV_FILE")
if env_file:
    env_path = Path(env_file)
    if not env_path.is_absolute():
        env_path = BASE_DIR / env_path
    env_repository = RepositoryEnv(str(env_path))
    fallback_config = AutoConfig(search_path=BASE_DIR)

    def config(name, default=None, cast=None):
        if name in env_repository.data:
            value = env_repository.data[name]
            if cast:
                return cast(value)
            return value
        if default is None:
            try:
                return fallback_config(name, cast=cast) if cast else fallback_config(name)
            except UndefinedValueError:
                raise
        return fallback_config(name, default=default, cast=cast) if cast else fallback_config(name, default=default)
else:
    config = AutoConfig(search_path=BASE_DIR)

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", cast=cast_bool, default=False)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv(), default="localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    cast=Csv(),
    default="http://localhost:5174,https://frontend-sdt.vercel.app",
)
ALLOWED_HOSTS = normalize_hosts(ALLOWED_HOSTS)

render_external_hostname = normalize_host(os.environ.get("RENDER_EXTERNAL_HOSTNAME", ""))
if render_external_hostname and render_external_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_external_hostname)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "apps.core",
    "apps.accounts",
    "apps.clients",
    "apps.catalog",
    "apps.physical",
    "apps.other_entries",
    "apps.other_cash_outflows",
    "apps.receivables",
    "apps.derivatives",
    "apps.strategies",
    "apps.marketdata",
    "apps.mercado",
    "apps.anotacoes",
    "apps.contrato",
    "apps.payables",
    "apps.risk",
    "apps.auditing",
    "apps.leads",
    "apps.agenda",
    "apps.tradingview_scraper",
    "apps.mass_update",
    "apps.insights",
    "apps.market_summary",
    "apps.gaming",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.auditing.middleware.AuditUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if not DEBUG:
    MIDDLEWARE.insert(2, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = config("DATABASE_URL", default="")

if DATABASE_URL:
    database_config = {
        "conn_max_age": 600,
    }
    if not DATABASE_URL.startswith("sqlite"):
        database_config["ssl_require"] = not DEBUG
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            **database_config,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="sdt_position"),
            "USER": config("DB_USER", default="postgres"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/min",
        "user": "1000/min",
        "login": "10/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=config("ACCESS_TOKEN_MINUTES", cast=int, default=30)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=config("REFRESH_TOKEN_DAYS", cast=int, default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    cast=Csv(),
    default="http://localhost:5174,https://frontend-sdt.vercel.app",
)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
    r"^https://frontend-sdt(?:-[a-z0-9-]+)?\.vercel\.app$",
]
CORS_ALLOWED_ORIGIN_REGEXES.extend(config("CORS_ALLOWED_ORIGIN_REGEXES_EXTRA", cast=Csv(), default=""))

FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:5174")
GOOGLE_CALENDAR_REDIRECT_URI = config("GOOGLE_CALENDAR_REDIRECT_URI", default="")
GOOGLE_CALENDAR_FRONTEND_URL = config("GOOGLE_CALENDAR_FRONTEND_URL", default=FRONTEND_URL)
ACCESS_REQUEST_NOTIFY_EMAIL = config("ACCESS_REQUEST_NOTIFY_EMAIL", default="evandrogoes@agrosaldaterra.com.br")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@sdt.local")
OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
OPENAI_INSIGHTS_MODEL = config("OPENAI_INSIGHTS_MODEL", default="gpt-5-mini")
OPENAI_MARKET_SUMMARY_MODEL = config("OPENAI_MARKET_SUMMARY_MODEL", default="gpt-5-mini")
AGRINVEST_USERNAME = config("AGRINVEST_USERNAME", default="")
AGRINVEST_PASSWORD = config("AGRINVEST_PASSWORD", default="")
AGRINVEST_CLIENT_ID = config("AGRINVEST_CLIENT_ID", default="D2365402-2F59-4627-A73D-71814F8FCCD2")
AGRINVEST_NEWS_URL = config("AGRINVEST_NEWS_URL", default="https://go.agrinvest.agr.br/noticias")
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", cast=int, default=25)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", cast=cast_bool, default=False)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", cast=cast_bool, default=False)

FILE_UPLOAD_MAX_MEMORY_SIZE = 10_485_760  # 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10_485_760

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", cast=cast_bool, default=True)
