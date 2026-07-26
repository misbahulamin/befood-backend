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

from .base import *

DEBUG = True

ALLOWED_HOSTS = [
    "*",
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3'
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


# CSRF settings
CSRF_TRUSTED_ORIGINS = [
    "https://befood-backend.onrender.com",
]


# Render HTTPS proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")