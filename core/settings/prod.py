from .base import *
DEBUG = False
ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='', cast=Csv())


# DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': config('DB_NAME'), 'USER': config('DB_USER'), 'PASSWORD': config('DB_PASSWORD'), 'HOST': config('DB_HOST', default='localhost'), 'PORT': config('DB_PORT', default='5432')}}

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

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
