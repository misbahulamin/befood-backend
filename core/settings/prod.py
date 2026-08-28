from .base import *
import os

DEBUG = False
# ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='', cast=Csv())
ALLOWED_HOSTS = [
    "befood.com.bd",
    "api.befood.com.bd",
    "43.204.109.243",
    "localhost",
    "127.0.0.1",
]

# Prefer host env / .env. Defaults match the last known production RDS wiring so
# # EC2 keeps working until DB_* are set explicitly on the server (then rotate).

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',       # Database name you created on RDS
        'USER': 'befood_postgres',   # The username you set for RDS
        'PASSWORD': 'Befood459',  # The password you set for RDS
        'HOST': 'befood.czais0km2ult.ap-south-1.rds.amazonaws.com',  # RDS endpoint
        'PORT': '5432',  # Default PostgreSQL port
    }
}

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': config('DB_NAME', default='befood_db'),
#         'USER': config('DB_USER', default='befood_postgres'),
#         'PASSWORD': config('DB_PASSWORD', default='Befood459'),
#         'HOST': config(
#             'DB_HOST',
#             default='befood-postgres-prod.c56oegiikk4d.ap-south-1.rds.amazonaws.com',
#         ),
#         'PORT': config('DB_PORT', default='5432'),
#     }
# }

# ---------------------------------------------------------------------------
# AWS S3 media — deferred until credentials are verified.
# Re-enable after S3 check: uncomment the import, validate_*, and STORAGES.
# ---------------------------------------------------------------------------
# from .aws_media import PROD_STORAGES, validate_aws_media_settings
#
# validate_aws_media_settings(
#     bucket_name=AWS_STORAGE_BUCKET_NAME,
#     region_name=AWS_S3_REGION_NAME,
# )
#
# STORAGES = PROD_STORAGES

_security_index = MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')
MIDDLEWARE = (
    MIDDLEWARE[: _security_index + 1]
    + ['whitenoise.middleware.WhiteNoiseMiddleware']
    + MIDDLEWARE[_security_index + 1 :]
)

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "ERROR",
        },
    },
}
