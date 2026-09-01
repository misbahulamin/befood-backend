from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY = config('SECRET_KEY', default='django-insecure-befood-development-key')
DEBUG = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
ALLOWED_HOSTS = ["api.befood.com.bd",'localhost', '127.0.0.1']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'storages',
    'corsheaders',
    'django_filters',
    'rest_framework',
    'rest_framework.authtoken',
    'drf_spectacular',
    'business',
    'core',
    'permissions',
    'user_management',
    'meals',
    'orders',
    'delivery',
    'payments',
    'wallet',
    'admin_wallet',
    'inventory',
    'service_area',
    'search',
    'notifications',
    'promotions',
    'notices',
    'announcements',
    'assets',
    'faqs',
    'blogs',
    'onahar',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': ['django.template.context_processors.debug', 'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']},
}]
WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Befood-Bachelors E-Food API',
    'DESCRIPTION': 'API documentation for Befood backend.',
    'VERSION': '1.0.0',
}

# --------------------------
# Static files (never on S3 media backend)
# --------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# --------------------------
# Media files (local filesystem by default; S3 when USE_S3_MEDIA=True)
# --------------------------
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --------------------------
# AWS S3 (media) — values from environment only; never hardcode secrets
# --------------------------
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='')
AWS_S3_CUSTOM_DOMAIN = config('AWS_S3_CUSTOM_DOMAIN', default='')
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}
USE_S3_MEDIA = config('USE_S3_MEDIA', default=False, cast=bool)

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.qiye.aliyun.com')
EMAIL_PORT = config('EMAIL_PORT', default=465, cast=int)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=True, cast=bool)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='support@befood.com.bd')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config(
    'DEFAULT_FROM_EMAIL',
    default='Befood <noreply@befood.com.bd>',
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_TIMEOUT = 30
FRONTEND_URL = config('FRONTEND_URL', default='https://www.befood.com.bd')

# Branded auth emails (absolute logo URL required for email clients).
EMAIL_LOGO_URL = config(
    'EMAIL_LOGO_URL',
    default=(
        'https://befood-media-storage.s3.ap-south-1.amazonaws.com/'
        'logo/befood_logo_for_template.png'
    ),
)
EMAIL_FACEBOOK_ICON_URL = config(
    'EMAIL_FACEBOOK_ICON_URL',
    default=(
        'https://befood-media-storage.s3.ap-south-1.amazonaws.com/'
        'logo/icon-facebook.png'
    ),
)
EMAIL_INSTAGRAM_ICON_URL = config(
    'EMAIL_INSTAGRAM_ICON_URL',
    default=(
        'https://befood-media-storage.s3.ap-south-1.amazonaws.com/'
        'logo/icon-instagram.png'
    ),
)
EMAIL_WHATSAPP_ICON_URL = config(
    'EMAIL_WHATSAPP_ICON_URL',
    default=(
        'https://befood-media-storage.s3.ap-south-1.amazonaws.com/'
        'logo/icon-whatsapp.png'
    ),
)
EMAIL_PLAY_STORE_URL = config(
    'EMAIL_PLAY_STORE_URL',
    default='https://play.google.com/store/apps/details?id=bd.com.befood',
)
EMAIL_PLAY_STORE_BADGE_URL = config(
    'EMAIL_PLAY_STORE_BADGE_URL',
    default='https://play.google.com/intl/en_us/badges/static/images/badges/en_badge_web_generic.png',
)
EMAIL_SITE_URL = config('EMAIL_SITE_URL', default='https://befood.com.bd')
EMAIL_PHONE = config('EMAIL_PHONE', default='+880 1751-678409')
EMAIL_WHATSAPP = config('EMAIL_WHATSAPP', default='+880 1751-678409')
EMAIL_FACEBOOK_URL = config(
    'EMAIL_FACEBOOK_URL',
    default='https://www.facebook.com/befoodbd',
)
EMAIL_INSTAGRAM_URL = config(
    'EMAIL_INSTAGRAM_URL',
    default='https://instagram.com/befoodbd',
)
EMAIL_ADDRESS = config(
    'EMAIL_ADDRESS',
    default=(
        'K.B Aman Ali Road, Boro Mia Masjid Goli, Bakolia., '
        'Chittagong, Bangladesh, 4203'
    ),
)
PASSWORD_RESET_FRONTEND_PATH = config(
    'PASSWORD_RESET_FRONTEND_PATH',
    default='/reset-password',
)
EMAIL_VERIFICATION_FRONTEND_PATH = config(
    'EMAIL_VERIFICATION_FRONTEND_PATH',
    default='/verify-email',
)
DELIVERYMAN_EMAIL_VERIFICATION_FRONTEND_PATH = config(
    'DELIVERYMAN_EMAIL_VERIFICATION_FRONTEND_PATH',
    default='/deliveryman/verify-email',
)

# Customer auth OTP (email verification + password reset). Plaintext never stored.
AUTH_OTP_TTL_SECONDS = config('AUTH_OTP_TTL_SECONDS', default=600, cast=int)
AUTH_OTP_MAX_ATTEMPTS = config('AUTH_OTP_MAX_ATTEMPTS', default=5, cast=int)
AUTH_OTP_RESEND_COOLDOWN_SECONDS = config(
    'AUTH_OTP_RESEND_COOLDOWN_SECONDS',
    default=60,
    cast=int,
)
AUTH_OTP_MAX_ISSUES_PER_HOUR = config(
    'AUTH_OTP_MAX_ISSUES_PER_HOUR',
    default=10,
    cast=int,
)

# Customer wallet: manual recharge/withdraw path (replace with gateway-only when ready).
WALLET_MANUAL_FUNDING_ENABLED = config(
    'WALLET_MANUAL_FUNDING_ENABLED',
    default=True,
    cast=bool,
)

# Debit customer wallet when an order delivery is marked delivered.
MEAL_DELIVERY_WALLET_CHARGE_ENABLED = config(
    'MEAL_DELIVERY_WALLET_CHARGE_ENABLED',
    default=True,
    cast=bool,
)

# Deprecated for cash accounting: meal charges must not cash-credit Admin Wallet
# (custody credits happen on customer recharge). Keep False unless emergency rollback.
ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED = config(
    'ADMIN_WALLET_MEAL_PAYMENT_CREDIT_ENABLED',
    default=False,
    cast=bool,
)

# Credit/debit BeFood Admin Wallet when a customer recharges/withdraws (custody).
ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED = config(
    'ADMIN_WALLET_CUSTOMER_FUNDING_CREDIT_ENABLED',
    default=True,
    cast=bool,
)

# Onahar charity campaign: credit points on delivered meals.
ONAHAR_ENABLED = config('ONAHAR_ENABLED', default=True, cast=bool)

# Reject meal package order create when delivery coords are outside active hubs.
SERVICE_AREA_ORDER_GATE_ENABLED = config(
    'SERVICE_AREA_ORDER_GATE_ENABLED',
    default=True,
    cast=bool,
)

# Soft GPS accuracy threshold (meters) for location_reliable on check API.
SERVICE_AREA_ACCURACY_THRESHOLD_M = config(
    'SERVICE_AREA_ACCURACY_THRESHOLD_M',
    default=500,
    cast=int,
)

# Emergency rollback: charge Order.per_meal_price_snapshot instead of published
# lunch/dinner slot final_meal_price_snapshot. Default False (slot pricing).
MEAL_DELIVERY_CHARGE_USE_ORDER_AVERAGE = config(
    'MEAL_DELIVERY_CHARGE_USE_ORDER_AVERAGE',
    default=False,
    cast=bool,
)

CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:5174',
    # Your frontend domain should be here
    'http://befood.com.bd',
    'https://befood.com.bd',
    'http://www.befood.com.bd',
    'https://www.befood.com.bd',
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
    "https://befood.com.bd",
    "https://api.befood.com.bd",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://api.befood.com.bd",
]

# --------------------------
# Firebase
# --------------------------
FIREBASE_CREDENTIALS = BASE_DIR / 'credentials' / 'firebase_service_account.json'
