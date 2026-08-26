# from .base import *
# DEBUG = True
# ALLOWED_HOSTS = ['*']
# DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
# INTERNAL_IPS = ['127.0.0.1']

# CORS_ALLOWED_ORIGINS = [
#     'http://localhost:5173',
#     'http://127.0.0.1:5173',
#     "https://befood-backend.onrender.com",
# ]

# # Local Postgres database (change values as needed)
# # DATABASES = {
# #     'default': {
# #         'ENGINE': 'django.db.backends.postgresql',
# #         'NAME': 'befood',
# #         'USER': 'befood',
# #         'PASSWORD': 'KxVjcWm8Uq5GccB6SnrywV6zSZ4iIONo',
# #         'HOST': 'dpg-d9hl836q1p3s73a4brrg-a.singapore-postgres.render.com',
# #         'PORT': '5432',
# #     }
# # }

# # CSRF_TRUSTED_ORIGINS = [
# #     "https://befood-backend.onrender.com",
# # ]

# CORS_ALLOW_CREDENTIALS = True
# CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

#------------------

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

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3'
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'befood_db',       # Database name you created on RDS
        'USER': 'befood_postgres',   # The username you set for RDS
        'PASSWORD': 'Befood459',  # The password you set for RDS
        'HOST': 'befood-postgres-prod.c56oegiikk4d.ap-south-1.rds.amazonaws.com',  # RDS endpoint
        'PORT': '5432',  # Default PostgreSQL port
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
