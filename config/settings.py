"""
Django settings for Gestion Billetterie project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Charge le fichier .env s'il existe (développement local)
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    raise RuntimeError("La variable d'environnement SECRET_KEY est obligatoire.")
SECRET_KEY = _secret_key

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

_allowed_hosts = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts.split(',') if h.strip()]

# ─── Synchronisation poste gare hors-ligne ↔ serveur central (apps.sync) ─────
# Utilisé uniquement côté poste gare (management commands sync_push/sync_pull) :
# URL du serveur central et jeton propre à cette gare (voir `create_gare_token`,
# à exécuter côté central). Laisser vide sur le serveur central lui-même.
SYNC_CENTRAL_URL = os.environ.get('SYNC_CENTRAL_URL', '')
SYNC_TOKEN = os.environ.get('SYNC_TOKEN', '')

# ─── Impression thermique ESC/POS (poste guichet local) ──────────────────────
# Le nom de l'imprimante et la largeur du ticket se configurent désormais
# depuis l'application (menu utilisateur → "Configuration Imprimante Ticket",
# champs sur apps.gares.models.Gare) — pas ici. IMPRIMANTE_BACKEND permet de
# tester sans imprimante physique : 'dummy' (aucune sortie) ou 'file' (écrit
# les octets ESC/POS bruts dans IMPRIMANTE_FICHIER_SORTIE pour inspection
# manuelle) ; 'win32raw' (par défaut) est l'impression réelle sur le poste.
IMPRIMANTE_BACKEND = os.environ.get('IMPRIMANTE_BACKEND', 'win32raw')
IMPRIMANTE_FICHIER_SORTIE = os.environ.get('IMPRIMANTE_FICHIER_SORTIE', '')



# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Sécurité
    'axes',
    'auditlog',
    'django_ratelimit',

    # Local apps
    'core',
    'apps.compagnie',
    'apps.gares',
    'apps.personnel',
    'apps.lignes',
    'apps.destinations',
    'apps.vehicules',
    'apps.programmes',
    'apps.voyages',
    'apps.billets',
    'apps.clients',
    'apps.guichet',
    'apps.comptabilite',
    'apps.sync',
    'apps.courrier',

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
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
                'apps.compagnie.context_processors.compagnie_context',
                'core.context_processors.active_module',
                'core.context_processors.modules_actifs',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Cache — Redis en prod, mémoire en développement
_cache_url = os.environ.get('CACHE_URL', '')
if _cache_url.startswith('redis://'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _cache_url,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

# En développement, le LocMemCache ne supporte pas l'incrément atomique
# (ratelimit fonctionne quand même sur un seul process — Redis règle ça en prod)
if DEBUG:
    SILENCED_SYSTEM_CHECKS = ['django_ratelimit.E003', 'django_ratelimit.W001']


# Database — PostgreSQL en prod (si DB_NAME défini), SQLite en local
if os.environ.get('DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME'),
            'USER': os.environ.get('DB_USER', 'otci_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Custom User Model
AUTH_USER_MODEL = 'personnel.Utilisateur'


# Password validation
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
LANGUAGE_CODE = 'fr-fr'

TIME_ZONE = 'Africa/Conakry'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (Uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Autorise les uploads jusqu'à 12 Mo (marge au-dessus de la limite métier de 10 Mo
# sur les documents chauffeurs, cf. apps/personnel/views.py). Doit rester cohérent
# avec client_max_body_size côté Nginx (voir DEPLOIEMENT_PRODUCTION.md, section 5.3).
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Login/Logout URLs
LOGIN_URL = 'personnel:login'
LOGIN_REDIRECT_URL = 'hub'
LOGOUT_REDIRECT_URL = 'personnel:login'

# ─── Django Axes (protection brute force) ────────────────────────────────────
AXES_FAILURE_LIMIT = 5           # Bloquer après 5 tentatives échouées
AXES_COOLOFF_TIME = 1            # Débloquer après 1 heure
AXES_LOCKOUT_CALLABLE = None
AXES_RESET_ON_SUCCESS = True     # Réinitialiser le compteur après succès
AXES_ENABLE_ADMIN = True
AXES_VERBOSE = False

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# ─── Sécurité des mots de passe ──────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Sessions sécurisées ─────────────────────────────────────────────────────
SESSION_COOKIE_AGE = 28800        # 8 heures
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'

# ─── Paramètres HTTPS (actifs en production uniquement) ─────────────────────
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True

X_FRAME_OPTIONS = 'DENY'
