"""
Django settings for oc project.

Generated by 'django-admin startproject' using Django 1.10.3.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.10/ref/settings/
"""

import dj_database_url
import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = 'oc_local_dev'

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'openCurrents.apps.OpencurrentsConfig',
    'macros',
    'django_extensions',
    'import_export',
    'django_admin_listfilter_dropdown'
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

    'openCurrents.middleware.AutoLogout',
]

ROOT_URLCONF = 'oc.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'oc.wsgi.application'


# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# sessions and auto-logout
AUTO_LOGOUT_DELAY = 180  # in minutes
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

STATIC_ROOT = os.path.join(PROJECT_ROOT, 'staticfiles')
MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'mediafiles')
CONTENT_TYPES = ['image', 'video']
MAX_UPLOAD_SIZE = 15 * 1024 * 1024

if os.getenv('GAE_INSTANCE') or os.getenv('GOOGLE_CLOUD_PROXY'):
    # Production
    DEBUG = False
    STATIC_URL = 'https://storage.googleapis.com/opencurrents-194003.appspot.com/static/'
    MEDIA_URL = 'https://storage.googleapis.com/opencurrents-194003.appspot.com/media/'

    # django-storages
    DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
    GS_BUCKET_NAME = 'opencurrents-194003.appspot.com'
    GS_PROJECT_ID = 'opencurrents-194003'
else:
    # Local Development
    # SECURITY WARNING: don't run with debug turned on in production!
    # TODO: change back once internal testing is complete
    DEBUG = True
    # STATIC_URL = 'https://storage.googleapis.com/opencurrents-194003.appspot.com/static/'
    # MEDIA_URL = 'https://storage.googleapis.com/opencurrents-194003.appspot.com/'

    STATIC_URL = '/static/'
    MEDIA_URL = '/media/'


APPEND_SLASH = True

# Extra places for collectstatic to find static files.
STATICFILES_DIRS = (
    os.path.join(PROJECT_ROOT, 'static'),
)

LOGIN_URL = 'openCurrents:login'

# [START dbconfig]
if os.getenv('OC_HEROKU_DEV'):
    # Update database configuration with $DATABASE_URL.
    db_from_env = dj_database_url.config(conn_max_age=500)
    DATABASES = {
        'default': db_from_env
    }
elif os.getenv('GAE_INSTANCE') or os.getenv('GOOGLE_CLOUD_PROXY'):
    DATABASES = {
        'default': {
            # If you are using Cloud SQL for MySQL rather than PostgreSQL, set
            # 'ENGINE': 'django.db.backends.mysql' instead of the following.
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'opencurrents',
            'USER': 'oc_admin',
            'PASSWORD': '0pencu44',
            # For MySQL, set 'PORT': '3306' instead of the following. Any Cloud
            # SQL Proxy instances running locally must also be set to tcp:3306.
            'PORT': '5432',
        }
    }

    # In the flexible environment, you connect to CloudSQL using a unix socket.
    # Locally, you can use the CloudSQL proxy to proxy a localhost connection
    # to the instance
    DATABASES['default']['HOST'] = '/cloudsql/opencurrents-194003:us-central1:oc-pg'
    if os.getenv('GAE_INSTANCE'):
        # when running on Google App Engine
        pass
    elif os.getenv('GOOGLE_CLOUD_PROXY'):
        # when using CloudSQL proxy to forward connections to remote db
        DATABASES['default']['HOST'] = '127.0.0.1'

# local db (sqlite)
else:
    # https://docs.djangoproject.com/en/1.10/ref/settings/#databases
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }
# [END dbconfig]

# do not send emails from local servers
SENDEMAILS = os.getenv('OC_SEND_EMAILS')
if os.getenv('GAE_INSTANCE'):
    SENDEMAILS = True
