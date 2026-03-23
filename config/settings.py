import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {'1', 'true', 'yes', 'on'}


def env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'change-me-6fA9zQp2LmN8vX4kRtY7uHi3sDwC0bJe5nPo1qRsTuVwXyZ',
)
DEBUG = env_bool('DEBUG', False)
ALLOWED_HOSTS = [host.strip() for host in os.environ.get('ALLOWED_HOSTS', 'localhost').split(',') if host.strip()]
IS_RENDER = env_bool('RENDER', False)


ADMIN_URL = (os.environ.get('ADMIN_URL', 'secure-admin/').strip().strip('/') or 'secure-admin') + '/'
STAFF_LOGIN_URL = (os.environ.get('STAFF_LOGIN_URL', 'staff-login/').strip().strip('/') or 'staff-login') + '/'
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()
]


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'akmalexpress',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'akmalexpress.middleware.LanguageMiddleware',
    'akmalexpress.middleware.NoIndexPrivateRoutesMiddleware',
    'akmalexpress.middleware.SecurityHeadersMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'akmalexpress.context_processors.language_context',
                'akmalexpress.context_processors.admin_track_notice_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('SQLITE_PATH') or (BASE_DIR / 'db.sqlite3'),
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'ru-ru'
LANGUAGES = [
    ('ru', 'Russian'),
    ('uz', 'Uzbek'),
]
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True


STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
default_media_root = Path('/var/data/media') if env_bool('RENDER', False) else (BASE_DIR / 'media')
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', str(default_media_root)))
SERVE_MEDIA_FILES = env_bool('SERVE_MEDIA_FILES', True)


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'staff_login'
LOGOUT_URL = 'logout'
LOGOUT_REDIRECT_URL = 'index'
LOGIN_REDIRECT_URL = 'index'


SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', IS_RENDER)
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', IS_RENDER)
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', IS_RENDER)
if IS_RENDER:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

LANGUAGE_COOKIE_SECURE = env_bool('LANGUAGE_COOKIE_SECURE', SESSION_COOKIE_SECURE)
LANGUAGE_COOKIE_HTTPONLY = env_bool('LANGUAGE_COOKIE_HTTPONLY', False)
LANGUAGE_COOKIE_SAMESITE = os.environ.get('LANGUAGE_COOKIE_SAMESITE', 'Lax')

STAFF_LOGIN_RATE_LIMIT_ATTEMPTS = max(1, env_int('STAFF_LOGIN_RATE_LIMIT_ATTEMPTS', 8))
STAFF_LOGIN_RATE_LIMIT_WINDOW_SECONDS = max(60, env_int('STAFF_LOGIN_RATE_LIMIT_WINDOW_SECONDS', 900))
STAFF_LOGIN_RATE_LIMIT_LOCK_SECONDS = max(60, env_int('STAFF_LOGIN_RATE_LIMIT_LOCK_SECONDS', 900))

CONTENT_SECURITY_POLICY = os.environ.get(
    'CONTENT_SECURITY_POLICY',
    "default-src 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "media-src 'self' blob: data:",
)

PERMISSIONS_POLICY = os.environ.get(
    'PERMISSIONS_POLICY',
    'accelerometer=(), autoplay=(), camera=(self), geolocation=(), gyroscope=(), '
    'magnetometer=(), microphone=(), payment=(), usb=()',
)
