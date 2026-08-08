from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY = config('SECRET_KEY', default='django-insecure-befood-development-key')
DEBUG = False
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
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
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
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
STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
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

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.qiye.aliyun.com'
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_USE_TLS = False
EMAIL_HOST_USER = 'misbahul@mypanaceatech.com'
EMAIL_HOST_PASSWORD = 'Towaha459@'
DEFAULT_FROM_EMAIL = 'Befood <misbahul@mypanaceatech.com>'
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_TIMEOUT = 30
FRONTEND_URL = 'http://localhost:5173'

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

# Emergency rollback: charge Order.per_meal_price_snapshot instead of published
# lunch/dinner slot final_meal_price_snapshot. Default False (slot pricing).
MEAL_DELIVERY_CHARGE_USE_ORDER_AVERAGE = config(
    'MEAL_DELIVERY_CHARGE_USE_ORDER_AVERAGE',
    default=False,
    cast=bool,
)
