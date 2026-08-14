import os
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
    FACE_MATCH_TOLERANCE=(float, 0.5),
)
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me-in-production')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[]) or [
    f'http://{h}' for h in ALLOWED_HOSTS if h != '*'
] + [
    f'https://{h}' for h in ALLOWED_HOSTS if h != '*'
]

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework.authtoken',
    'django_celery_results',
    # Local apps
    'config.apps.ConfigApp',
    'accounts',
    'events',
    'photos',
    'guests',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
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
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ── Database — MongoDB for EVERYTHING (auth, sessions, tokens, app data) ──
DATABASES = {
    'default': {
        'ENGINE': 'django_mongodb_backend',
        'NAME': env('MONGO_DB', default='zayrosnap'),
        'HOST': env('MONGO_HOST', default='localhost'),
        'PORT': env.int('MONGO_PORT', default=27017),
    }
}

DEFAULT_AUTO_FIELD = 'django_mongodb_backend.fields.ObjectIdAutoField'

# Custom user model — uses MongoDB ObjectId as PK
AUTH_USER_MODEL = 'accounts.User'

# Silence AutoField/ObjectId mismatch warnings for third-party apps
SILENCED_SYSTEM_CHECKS = ['mongodb.E001']

# Skip ORM migrations for our app models — managed directly by pymongo
MIGRATION_MODULES = {
    'events': None,
    'photos': None,
    'guests': None,
}

# Upload limits — DATA_UPLOAD_MAX_MEMORY_SIZE accepts None, FILE_UPLOAD_MAX_MEMORY_SIZE does not
DATA_UPLOAD_MAX_MEMORY_SIZE  = None          # no limit on form data size
FILE_UPLOAD_MAX_MEMORY_SIZE  = 2621440       # 2.5 MB — files larger than this stream to disk (Django default)
DATA_UPLOAD_MAX_NUMBER_FILES = None          # no limit on number of files

# ── MongoDB (pymongo direct access via mongo_store.py) ───────────────────
SITE_URL = env('SITE_URL', default='http://localhost:8000')
MONGO_URI = env('MONGO_URI', default='')
MONGO_HOST = env('MONGO_HOST', default='localhost')
MONGO_PORT = env.int('MONGO_PORT', default=27017)
MONGO_DB = env('MONGO_DB', default='zayrosnap')
MONGO_USER = env('MONGO_USER', default='')
MONGO_PASSWORD = env('MONGO_PASSWORD', default='')
MONGO_AUTH_SOURCE = env('MONGO_AUTH_SOURCE', default='admin')

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Celery
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False

# Auth redirects
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Face recognition
FACE_MATCH_TOLERANCE = env('FACE_MATCH_TOLERANCE')

# Thumbnail size
THUMBNAIL_SIZE = (400, 400)
