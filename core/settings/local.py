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

# INTERNAL_IPS = ['127.0.0.1']


# CORS settings


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
