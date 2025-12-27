# ruff: noqa: E501
import logging
import os
import warnings

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration

from .base import *  # noqa: F403
from .base import DATABASES
from .base import INSTALLED_APPS
from .base import REDIS_URL
from .base import SPECTACULAR_SETTINGS
from .base import env


# ------------------------------------------------------------------------------
# ASGI + WhiteNoise
# ------------------------------------------------------------------------------
# En production on sert Django via ASGI (gunicorn + uvicorn worker) pour supporter
# les websockets. WhiteNoise est un middleware WSGI-oriented et, sous ASGI, Django
# émet un warning à chaque réponse streamée (typiquement /static/* de l'admin).
# Ce warning est non-bloquant mais spamme les logs.
warnings.filterwarnings(
    "ignore",
    message=r"StreamingHttpResponse must consume synchronous iterators.*",
    category=Warning,
    module=r"django\.core\.handlers\.asgi",
)

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env("DJANGO_SECRET_KEY")
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["api.fox-reviews.com", "fox-reviews.com", "www.fox-reviews.com"],
)

# CSRF / CORS
# ------------------------------------------------------------------------------
# Traefik termine TLS et reverse-proxy vers Django. Pour les requêtes navigateur
# (admin, docs, front), on doit expliciter les origines de confiance.
CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=[
        "https://api.fox-reviews.com",
        "https://fox-reviews.com",
        "https://www.fox-reviews.com",
    ],
)

# Si le front consomme l'API depuis un autre domaine, activer CORS.
# NOTE: On utilise env.list pour permettre un override simple via .envs/.production/.django
CORS_ALLOWED_ORIGINS = env.list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    default=[
        "https://fox-reviews.com",
        "https://www.fox-reviews.com",
    ],
)
CORS_ALLOW_CREDENTIALS = env.bool("DJANGO_CORS_ALLOW_CREDENTIALS", default=True)

# Observability
# ------------------------------------------------------------------------------
PROMETHEUS_METRICS_ENABLED = env.bool("PROMETHEUS_METRICS_ENABLED", default=True)

# DATABASES
# ------------------------------------------------------------------------------
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)

# CACHES
# ------------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # Mimicking memcache behavior.
            # https://github.com/jazzband/django-redis#memcached-exceptions-behavior
            "IGNORE_EXCEPTIONS": True,
        },
    },
}

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-proxy-ssl-header
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-ssl-redirect
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-secure
SESSION_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-name
SESSION_COOKIE_NAME = "__Secure-sessionid"
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-secure
CSRF_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-name
CSRF_COOKIE_NAME = "__Secure-csrftoken"
# https://docs.djangoproject.com/en/dev/topics/security/#ssl-https
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-seconds
# TODO: set this to 60 seconds first and then to 518400 once you prove the former works
SECURE_HSTS_SECONDS = 60
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-include-subdomains
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=True,
)
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-preload
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=True)
# https://docs.djangoproject.com/en/dev/ref/middleware/#x-content-type-options-nosniff
SECURE_CONTENT_TYPE_NOSNIFF = env.bool(
    "DJANGO_SECURE_CONTENT_TYPE_NOSNIFF",
    default=True,
)

# PASSWORD HASHING
# ------------------------------------------------------------------------------
# Argon2 is great but can be too memory-hungry on small servers/containers and may
# trigger OOM kills during login when multiple workers verify passwords.
# In production we prefer PBKDF2 as the default hasher (new passwords), while
# keeping Argon2 enabled to verify existing hashes and let Django auto-upgrade
# them to the preferred hasher on successful login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]


# Optional external services (we don't require AWS/Mailgun/Sentry)
# ------------------------------------------------------------------------------
USE_S3_STORAGE = env.bool("DJANGO_USE_S3_STORAGE", default=False)
USE_MAILGUN = env.bool("DJANGO_USE_MAILGUN", default=False)
USE_SENTRY = env.bool("DJANGO_USE_SENTRY", default=False)


if USE_S3_STORAGE:
    # https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
    AWS_ACCESS_KEY_ID = env("DJANGO_AWS_ACCESS_KEY_ID")
    # https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
    AWS_SECRET_ACCESS_KEY = env("DJANGO_AWS_SECRET_ACCESS_KEY")
    # https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
    AWS_STORAGE_BUCKET_NAME = env("DJANGO_AWS_STORAGE_BUCKET_NAME")
    # https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
    AWS_QUERYSTRING_AUTH = False
    # DO NOT change these unless you know what you're doing.
    _AWS_EXPIRY = 60 * 60 * 24 * 7
    # https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": f"max-age={_AWS_EXPIRY}, s-maxage={_AWS_EXPIRY}, must-revalidate",
    }
    # https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
    AWS_S3_MAX_MEMORY_SIZE = env.int(
        "DJANGO_AWS_S3_MAX_MEMORY_SIZE",
        default=100_000_000,  # 100MB
    )
    # https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
    AWS_S3_REGION_NAME = env("DJANGO_AWS_S3_REGION_NAME", default=None)
    # https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#cloudfront
    AWS_S3_CUSTOM_DOMAIN = env("DJANGO_AWS_S3_CUSTOM_DOMAIN", default=None)
    aws_s3_domain = AWS_S3_CUSTOM_DOMAIN or f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"

    # STATIC & MEDIA
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "location": "media",
                "file_overwrite": False,
            },
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "location": "static",
                "default_acl": "public-read",
            },
        },
    }
    MEDIA_URL = f"https://{aws_s3_domain}/media/"
    STATIC_URL = f"https://{aws_s3_domain}/static/"
    COLLECTFASTA_STRATEGY = "collectfasta.strategies.boto3.Boto3Strategy"
else:
    # Keep local/static defaults from base settings:
    # - STATIC_URL=/static/ and STATIC_ROOT=.../staticfiles
    # - MEDIA_URL=/media/ and MEDIA_ROOT=.../foxreviews/media
    # (No extra env vars required)
    pass

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#default-from-email
DEFAULT_FROM_EMAIL = env(
    "DJANGO_DEFAULT_FROM_EMAIL",
    default="foxreviews <noreply@fox-reviews.com>",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#server-email
SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-subject-prefix
EMAIL_SUBJECT_PREFIX = env(
    "DJANGO_EMAIL_SUBJECT_PREFIX",
    default="[foxreviews] ",
)
ACCOUNT_EMAIL_SUBJECT_PREFIX = EMAIL_SUBJECT_PREFIX

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL regex.
ADMIN_URL = env("DJANGO_ADMIN_URL")

# Anymail
# ------------------------------------------------------------------------------
if USE_MAILGUN:
    # https://anymail.readthedocs.io/en/stable/installation/#installing-anymail
    INSTALLED_APPS += ["anymail"]
    # https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
    # https://anymail.readthedocs.io/en/stable/esps/mailgun/
    EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
    ANYMAIL = {
        "MAILGUN_API_KEY": env("MAILGUN_API_KEY"),
        "MAILGUN_SENDER_DOMAIN": env("MAILGUN_DOMAIN"),
        "MAILGUN_API_URL": env("MAILGUN_API_URL", default="https://api.mailgun.net/v3"),
    }
else:
    # No Mailgun configured: keep email working without external provider.
    EMAIL_BACKEND = env(
        "DJANGO_EMAIL_BACKEND",
        default="django.core.mail.backends.console.EmailBackend",
    )

# django-compressor
# ------------------------------------------------------------------------------
# https://django-compressor.readthedocs.io/en/latest/settings/#django.conf.settings.COMPRESS_ENABLED
# En prod, on évite les 500 côté templates si django-compressor est activé mais
# que la config storage n'est pas disponible (ex: S3 désactivé).
COMPRESS_OFFLINE = env.bool("COMPRESS_OFFLINE", default=False)
COMPRESS_ENABLED = env.bool("COMPRESS_ENABLED", default=False)

# Important:
# - Avec WhiteNoise, la génération "on the fly" des fichiers COMPRESS (CACHE/*)
#   après le démarrage n'est pas servie, car WhiteNoise indexe les fichiers au boot.
# - Si vous voulez utiliser compressor en prod, utilisez le mode offline:
#   `COMPRESS_OFFLINE=True` + exécution du management command `compress`.
if COMPRESS_OFFLINE:
    COMPRESS_ENABLED = True
else:
    # Empêche les CSS/JS cassés en prod si quelqu'un active COMPRESS_ENABLED
    # sans pipeline offline.
    COMPRESS_ENABLED = False

# https://django-compressor.readthedocs.io/en/latest/settings/#django.conf.settings.COMPRESS_STORAGE
if USE_S3_STORAGE:
    COMPRESS_STORAGE = STORAGES["staticfiles"]["BACKEND"]
else:
    COMPRESS_STORAGE = env(
        "COMPRESS_STORAGE",
        default="compressor.storage.CompressorFileStorage",
    )
# https://django-compressor.readthedocs.io/en/latest/settings/#django.conf.settings.COMPRESS_URL
COMPRESS_URL = STATIC_URL
# https://django-compressor.readthedocs.io/en/latest/settings/#django.conf.settings.COMPRESS_FILTERS
COMPRESS_FILTERS = {
    "css": [
        "compressor.filters.css_default.CssAbsoluteFilter",
        "compressor.filters.cssmin.rCSSMinFilter",
    ],
    "js": ["compressor.filters.jsmin.JSMinFilter"],
}
# Collectfasta
# ------------------------------------------------------------------------------
# https://github.com/jasongi/collectfasta#installation
if USE_S3_STORAGE:
    INSTALLED_APPS = ["collectfasta", *INSTALLED_APPS]

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.

LOG_LEVEL = env("DJANGO_LOG_LEVEL", default="INFO")
LOG_TO_FILE = env.bool("DJANGO_LOG_TO_FILE", default=True)
LOG_FILE = env("DJANGO_LOG_FILE", default="/app/logs/django-error.log")

LOG_HANDLERS = ["console"]
LOGGING_HANDLERS = {
    "console": {
        "level": "DEBUG",
        "class": "logging.StreamHandler",
        "formatter": "verbose",
    },
}

if LOG_TO_FILE:
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    LOG_HANDLERS.append("file")
    LOGGING_HANDLERS["file"] = {
        "level": "ERROR",
        "class": "logging.handlers.RotatingFileHandler",
        "formatter": "verbose",
        "filename": LOG_FILE,
        "maxBytes": env.int("DJANGO_LOG_FILE_MAX_BYTES", default=10_000_000),
        "backupCount": env.int("DJANGO_LOG_FILE_BACKUP_COUNT", default=10),
    }

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": LOGGING_HANDLERS,
    "root": {"level": LOG_LEVEL, "handlers": LOG_HANDLERS},
    "loggers": {
        "django.db.backends": {
            "level": "ERROR",
            "handlers": LOG_HANDLERS,
            "propagate": False,
        },
        "django.request": {
            "level": "ERROR",
            "handlers": LOG_HANDLERS,
            "propagate": False,
        },
        "django.server": {
            "level": "ERROR",
            "handlers": LOG_HANDLERS,
            "propagate": False,
        },
        # Errors logged by the SDK itself
        "sentry_sdk": {"level": "ERROR", "handlers": LOG_HANDLERS, "propagate": False},
        "django.security.DisallowedHost": {
            "level": "ERROR",
            "handlers": LOG_HANDLERS,
            "propagate": False,
        },
    },
}

if USE_SENTRY:
    # Sentry
    # ------------------------------------------------------------------------------
    SENTRY_DSN = env("SENTRY_DSN", default="")
    if SENTRY_DSN:
        SENTRY_LOG_LEVEL = env.int("DJANGO_SENTRY_LOG_LEVEL", logging.INFO)

        sentry_logging = LoggingIntegration(
            level=SENTRY_LOG_LEVEL,  # Capture info and above as breadcrumbs
            event_level=logging.ERROR,  # Send errors as events
        )
        integrations = [
            sentry_logging,
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ]
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=integrations,
            environment=env("SENTRY_ENVIRONMENT", default="production"),
            traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
        )

# django-rest-framework
# -------------------------------------------------------------------------------
# Tools that generate code samples can use SERVERS to point to the correct domain
SPECTACULAR_SETTINGS["SERVERS"] = [
    {"url": "https://api.fox-reviews.com", "description": "Production API server"},
]
# Your stuff...
# ------------------------------------------------------------------------------
