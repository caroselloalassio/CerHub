# cercollettiva/settings/cloudron.py
#
# Impostazioni per l'esecuzione come app Cloudron.
# Tutti i parametri arrivano dagli addon Cloudron (postgresql, redis, sendmail,
# localstorage) tramite variabili d'ambiente CLOUDRON_*; i segreti generati al
# primo avvio stanno in /app/data.

import os
import socket
from pathlib import Path

from .base import *  # noqa: F401,F403

ENVIRONMENT = 'production'
DEBUG = False

DATA_DIR = Path(os.getenv('CERHUB_DATA_DIR', '/app/data'))
RUN_DIR = Path(os.getenv('CERHUB_RUN_DIR', '/run/cerhub'))

# --- Segreti (generati da start.sh al primo avvio) ---------------------------
SECRET_KEY = os.environ['SECRET_KEY']
FIELD_ENCRYPTION_KEY = os.environ['FIELD_ENCRYPTION_KEY']

# --- Host ---------------------------------------------------------------------
APP_DOMAIN = os.getenv('CLOUDRON_APP_DOMAIN', 'localhost')
APP_ORIGIN = os.getenv('CLOUDRON_APP_ORIGIN', f'https://{APP_DOMAIN}')

ALLOWED_HOSTS = [APP_DOMAIN, 'localhost', '127.0.0.1']
try:
    # IP del container: usato dall'healthcheck di Cloudron
    _hostname, _aliases, _ips = socket.gethostbyname_ex(socket.gethostname())
    ALLOWED_HOSTS.extend([_hostname] + _ips)
except OSError:
    pass
ALLOWED_HOSTS.extend(h for h in os.getenv('ALLOWED_HOSTS', '').split(',') if h)

CSRF_TRUSTED_ORIGINS = [APP_ORIGIN]

# --- Applicazioni e middleware ------------------------------------------------
# Google Analytics dell'associazione CER Hub (flusso "app.cerhub.it");
# viene caricato solo dopo il consenso dell'utente. Vuoto = disattivato.
GA_MEASUREMENT_ID = os.getenv('GA_MEASUREMENT_ID', 'G-DD20KVR90S')
TEMPLATES[0]['OPTIONS']['context_processors'].append('cercollettiva.cloudron_context.analytics')

MIDDLEWARE = MIDDLEWARE + [
    # Al primo accesso, se non esiste un amministratore, porta al setup iniziale
    'core.middleware.FirstInstallationMiddleware',
]

# --- Database (addon postgresql) ----------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['CLOUDRON_POSTGRESQL_DATABASE'],
        'USER': os.environ['CLOUDRON_POSTGRESQL_USERNAME'],
        'PASSWORD': os.environ['CLOUDRON_POSTGRESQL_PASSWORD'],
        'HOST': os.environ['CLOUDRON_POSTGRESQL_HOST'],
        'PORT': os.getenv('CLOUDRON_POSTGRESQL_PORT', '5432'),
        'CONN_MAX_AGE': 600,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {'connect_timeout': 10},
    }
}

# --- Cache e Channels (addon redis) -------------------------------------------
REDIS_URL = os.environ['CLOUDRON_REDIS_URL']

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        'KEY_PREFIX': 'cerhub',
    }
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [REDIS_URL]},
    },
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_COOKIE_AGE = 86400
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# --- Email (addon sendmail) ---------------------------------------------------
if os.getenv('CLOUDRON_MAIL_SMTP_SERVER'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ['CLOUDRON_MAIL_SMTP_SERVER']
    EMAIL_PORT = int(os.getenv('CLOUDRON_MAIL_SMTP_PORT', '2525'))
    EMAIL_HOST_USER = os.getenv('CLOUDRON_MAIL_SMTP_USERNAME', '')
    EMAIL_HOST_PASSWORD = os.getenv('CLOUDRON_MAIL_SMTP_PASSWORD', '')
    EMAIL_USE_TLS = False
    EMAIL_USE_SSL = False
    DEFAULT_FROM_EMAIL = os.getenv('CLOUDRON_MAIL_FROM', f'noreply@{APP_DOMAIN}')
    SERVER_EMAIL = DEFAULT_FROM_EMAIL
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# --- File statici e caricati ---------------------------------------------------
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'cercollettiva.cloudron_storage.TolerantManifestStaticFilesStorage'
MEDIA_ROOT = DATA_DIR / 'media'
MEDIA_URL = '/media/'
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_TEMP_DIR = str(RUN_DIR / 'tmp')

# --- Sicurezza ----------------------------------------------------------------
# Cloudron termina TLS sul proprio reverse proxy e reindirizza già http -> https.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False
USE_X_FORWARDED_HOST = False
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_HSTS_SECONDS = 31536000

# --- Geocoding ----------------------------------------------------------------
GEOCODING_SETTINGS = {
    'TIMEOUT': 5,
    'MAX_RETRIES': 2,
    'OPTIONAL': True,
    'CACHE_TIMEOUT': 86400,
}

# --- Logging: su stdout/stderr (raccolto da Cloudron); i file scritti
# direttamente dal codice (accessi, MQTT) finiscono in /app/data/logs ---------
LOGS_DIR = DATA_DIR / 'logs'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'django.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'core': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'users': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'energy': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'energy.mqtt': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'energy.measurements': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'energy.devices': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'documents': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'geocoding': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'gaudi': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
}

CRISPY_FAIL_SILENTLY = True
