import importlib.resources
import json
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/stable/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-a-very-secret-key"  # noqa: S105

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "False") == "True"

ALLOWED_HOSTS = [
    "*",
    # for intance #  ".localhost",
    # for intance #  "127.0.0.1",
    # for intance #  "[::1]",
    # for intance #  # FIXME: WJS pages on my machine setup
    # for intance #  "https://jcom.localdomain.net",
    # for intance #  # FIXME: Weasel WebSocket Client (firefox extension)
    # for intance #  "moz-extension://954122f5-c407-4878-b409-44578cabac73",
]


# Application definition

INSTALLED_APPS = [
    "daphne",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "yakunin_service.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

ASGI_APPLICATION = "yakunin_service.asgi.application"
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, 6379)],
        },
    },
}


# Password validation
# https://docs.djangoproject.com/en/stable/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/stable/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/stable/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/stable/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


def load_logging_config():
    """Load logging configuration from yakunin.json file."""
    fallback = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
                "style": "{",
            },
        },
        "handlers": {
            "console": {
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            },
        },
        "root": {
            "handlers": ["console"],
        },
        "loggers": {
            "yakunin": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }
    try:
        config_file = importlib.resources.files("yakunin") / "yakunin.json"
        with open(config_file, encoding="utf-8") as f:
            config = json.load(f)
            return config.get("LOGGING", fallback)
    except FileNotFoundError:
        print(f"Warning: {config_file} not found. Using default logging configuration.")
        return fallback
    except json.JSONDecodeError:
        print(f"Warning: Invalid JSON in {config_file}. Using default logging configuration.")
        return fallback


LOGGING = load_logging_config()
