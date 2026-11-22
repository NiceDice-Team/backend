import os, stripe

from pathlib import Path
from corsheaders.defaults import default_headers
from dotenv import load_dotenv
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

local_env = BASE_DIR / 'local.env'
prod_env = BASE_DIR / 'dev.env'
load_dotenv(local_env if local_env.exists() else prod_env)

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-key')
DEBUG = os.getenv('DEBUG', 'false').lower() in {'1', 'true', 'yes', 'on'}
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'backend,localhost,127.0.0.1').split(',')
SITE_BASE_URL = os.getenv('SITE_BASE_URL', '').strip()
FRONTEND_BASE_URL = os.getenv('FRONTEND_BASE_URL', 'https://team-challange-front.vercel.app').strip()

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third‑party
    'rest_framework',
    'drf_spectacular',
    'drf_spectacular_sidecar',
    'corsheaders',
    'storages',

    # JWT blacklist app
    'rest_framework_simplejwt.token_blacklist',

    # Standardized errors for DRF + OpenAPI
    'drf_standardized_errors',

    # Project apps
    'products',
    'categories',
    'orders',
    'users',
    'cart',
    'core',
]

STORAGES = {
    "default": {
        "BACKEND": "src.s3.MediaStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# -----------------------------------
# Email settings
# -----------------------------------
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')


def getenv_bool(name: str, default: bool = False) -> bool:
    """Return boolean value parsed from environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {'1', 'true', 'yes', 'on'}


def getenv_csv(name: str, default: str = '') -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(',') if item.strip()]


EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = getenv_bool('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = getenv_bool('EMAIL_USE_SSL', False)
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '10'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'webmaster@localhost')
REPLY_TO_EMAIL = os.getenv('REPLY_TO_EMAIL', DEFAULT_FROM_EMAIL)

# -----------------------------------
# DRF + drf-standardized-errors
# -----------------------------------
REST_FRAMEWORK = {
    # Use an exception handler from drf-standardized-errors
    'EXCEPTION_HANDLER': 'drf_standardized_errors.handler.exception_handler',

    # To generate an error pattern via drf-standardized-errors
    'DEFAULT_SCHEMA_CLASS': 'common.openapi.ApiAutoSchema',

    'DEFAULT_PARSER_CLASSES': [
        'common.parsers.JSONObjectParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],

    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],

    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,

    # --- Search & sort ---
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],

    # Throttling setup
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'forgot-password': '5/hour',
        'login': '10/minute',
        'guest-checkout': '100/hour',
        'guest-cart': '100/hour',
        'register': '5/hour',
        'resend-activation': '5/hour',
    },
}

DRF_STANDARDIZED_ERRORS = {
    'EXCEPTION_HANDLER_CLASS': 'common.exceptions.ApiExceptionHandler',
    'ALLOWED_ERROR_STATUS_CODES': ['400', '401', '403', '404', '405', '406', '409', '415', '429', '500'],
    'ERROR_SCHEMAS': {
        '401': 'common.openapi.ErrorResponse401Serializer',
        '409': 'common.openapi.ErrorResponse409Serializer',
    },
}

# -----------------------------------
# drf-spectacular
# -----------------------------------
SPECTACULAR_SETTINGS = {
    'TITLE': 'Board Game Shop',
    'DESCRIPTION': 'Board Game Shop API',
    'VERSION': '1.0.0',

    # Add descriptions for HTTP error codes
    'ENUM_NAME_OVERRIDES': {
        "ValidationErrorEnum": "drf_standardized_errors.openapi_serializers.ValidationErrorEnum.choices",
        "ClientErrorEnum": "drf_standardized_errors.openapi_serializers.ClientErrorEnum.choices",
        "ServerErrorEnum": "drf_standardized_errors.openapi_serializers.ServerErrorEnum.choices",
        "ErrorCode401Enum": "drf_standardized_errors.openapi_serializers.ErrorCode401Enum.choices",
        "ErrorCode409Enum": "common.openapi.ErrorCode409Enum.choices",
        "OrderStatusEnum": "orders.infrastructure.models.ORDER_STATUS_CHOICES",
        "ErrorCode403Enum": "drf_standardized_errors.openapi_serializers.ErrorCode403Enum.choices",
        "ErrorCode404Enum": "drf_standardized_errors.openapi_serializers.ErrorCode404Enum.choices",
    },
    # Hook to correctly substitute error enums into the schema
    'POSTPROCESSING_HOOKS': [
        'drf_standardized_errors.openapi_hooks.postprocess_schema_enums'
    ],
    'SERVE_INCLUDE_SCHEMA': False,
    'PATH_CONVERTER_OVERRIDES': {
        'id': {'type': 'integer', 'format': 'int64', 'minimum': 0, 'maximum': 9223372036854775807},
    },
}

# Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'PASSWORD_RESET_TIMEOUT': 3600,
}

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'src.security.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'src.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'src.wsgi.application'

CORS_ALLOW_ALL_ORIGINS = getenv_bool('CORS_ALLOW_ALL_ORIGINS', False)
CORS_ALLOW_CREDENTIALS = getenv_bool('CORS_ALLOW_CREDENTIALS', True)
CORS_URLS_REGEX = r'^/api/.*$'

_default_cors_origins = 'http://localhost:3000,http://127.0.0.1:3001'
if FRONTEND_BASE_URL:
    _default_cors_origins = f'{_default_cors_origins},{FRONTEND_BASE_URL}'

_cors_allowed_origins = getenv_csv('CORS_ALLOWED_ORIGINS', _default_cors_origins)
if _cors_allowed_origins:
    CORS_ALLOWED_ORIGINS = _cors_allowed_origins

_cors_allowed_origin_regexes = getenv_csv('CORS_ALLOWED_ORIGIN_REGEXES')
if _cors_allowed_origin_regexes:
    CORS_ALLOWED_ORIGIN_REGEXES = _cors_allowed_origin_regexes

_cors_extra_headers = getenv_csv(
    'CORS_ALLOW_HEADERS_EXTRA',
    'x-guest-token,cache-control',
)
CORS_ALLOW_HEADERS = [*default_headers, *_cors_extra_headers]

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = os.getenv('X_FRAME_OPTIONS', 'DENY')
SECURE_HSTS_SECONDS = int(
    os.getenv('SECURE_HSTS_SECONDS', '31536000' if not DEBUG else '0')
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = getenv_bool(
    'SECURE_HSTS_INCLUDE_SUBDOMAINS',
    True,
)
SECURE_HSTS_PRELOAD = getenv_bool('SECURE_HSTS_PRELOAD', False)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'postgres'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': os.getenv('DB_SSLMODE', 'disable')
        },
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
AUTH_USER_MODEL = 'users.User'

# Google OAuth https://console.cloud.google.com/
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.getenv('GOOGLE_OAUTH2_CLIENT_ID', '')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.getenv('GOOGLE_OAUTH2_CLIENT_SECRET', '')

# Facebook OAuth https://developers.facebook.com/
SOCIAL_AUTH_FACEBOOK_KEY = os.getenv('FACEBOOK_APP_ID', '')
SOCIAL_AUTH_FACEBOOK_SECRET = os.getenv('FACEBOOK_APP_SECRET', '')

STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
STRIPE_DEMO_MODE = getenv_bool('STRIPE_DEMO_MODE', False)
stripe.api_key = STRIPE_SECRET_KEY

FRONTEND_URL = os.getenv('FRONTEND_URL', FRONTEND_BASE_URL or 'https://team-challange-front-yx5j.vercel.app')
BACKEND_URL = os.getenv('BACKEND_URL', SITE_BASE_URL or 'https://bgshop.work.gd')

# -----------------------------------
# Account activation TTL
# -----------------------------------
ACTIVATION_ACCOUNT_TTL_DAYS = 3
PASSWORD_RESET_TIMEOUT = 3 * 24 * 60 * 60

# -----------------------------------
# Order confirmation email URLs
# -----------------------------------
ORDER_EMAIL_LOGO_ICON_URL = 'https://images.icon-icons.com/37/PNG/512/dice_3293.png'
ORDER_EMAIL_LOGO_IMAGE_URL = 'https://placehold.co/150x40?text=Dice+%26+Decks'
ORDER_EMAIL_CANCEL_ICON_URL = 'https://img.icons8.com/ios/50/last-48-hours.png'

ORDER_EMAIL_VIEW_ORDER_URL_TEMPLATE = FRONTEND_URL.rstrip('/') + '/profile'
ORDER_EMAIL_CANCEL_ORDER_URL_TEMPLATE = BACKEND_URL.rstrip("/") + "/api/orders/{order_id}/cancel/?token={token}"
ORDER_EMAIL_PRODUCT_URL_TEMPLATE = FRONTEND_URL.rstrip('/') + '/product/{product_id}'
