import sys

from .base import *

DEBUG = True

# Existing order tests create packages without delivery coordinates / hubs.
# Dedicated service_area gate tests re-enable via override_settings.
if len(sys.argv) > 1 and sys.argv[1] == 'test':
    SERVICE_AREA_ORDER_GATE_ENABLED = False

ALLOWED_HOSTS = [
    "*",
]

# Local Postgres via environment (see .env.example). Do not point at production RDS.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='befood'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='postgres'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

INTERNAL_IPS = ['127.0.0.1']


# CORS settings
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    # Your frontend domain should be here
    'http://befood.com.bd',
    'https://befood.com.bd',
]

CORS_ALLOW_CREDENTIALS = True

# Default corsheaders list + wallet funding / multi-client headers.
# Without these, browsers complete OPTIONS then block POST (axios "Network Error").
CORS_ALLOW_HEADERS = [
    'accept',
    'authorization',
    'content-type',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'idempotency-key',
    'x-client-type',
    'x-guest-session-id',
]


# CSRF settings
CSRF_TRUSTED_ORIGINS = [
    "https://befood-backend.onrender.com",
]

# Render HTTPS proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Optional: set USE_S3_MEDIA=true in .env to test S3 uploads locally.
if USE_S3_MEDIA:
    from .aws_media import LOCAL_S3_STORAGES, validate_aws_media_settings

    validate_aws_media_settings(
        bucket_name=AWS_STORAGE_BUCKET_NAME,
        region_name=AWS_S3_REGION_NAME,
    )
    STORAGES = LOCAL_S3_STORAGES
