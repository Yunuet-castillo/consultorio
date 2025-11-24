"""
Django settings for sistema_citas project.
"""

import os
import dj_database_url
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================
# 🔐 SEGURIDAD
# ============================================================

SECRET_KEY = 'django-insecure-=r@=@&hm0jsgn74zg1i*5w7w#nvbdfozpw12@9l2)qpcrz+f9l'

# ⚠️ Render pondrá DEBUG=False automáticamente
DEBUG = os.getenv("RENDER", None) != "true"

ALLOWED_HOSTS = ['*']


# ============================================================
# 🧩 APPS
# ============================================================

INSTALLED_APPS = [
    'jet.dashboard',
    'jet',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    'citas',

    'rest_framework',
    'rest_framework.authtoken',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    )
}


# ============================================================
# 🧱 MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    # Necesario para Render (manejo de archivos estáticos)
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sistema_citas.urls'


# ============================================================
# 🎨 TEMPLATES
# ============================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                "django.template.context_processors.debug",
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sistema_citas.wsgi.application'


# ============================================================
# 🗄️ BASE DE DATOS (LOCAL + RENDER)
# ============================================================

# Base local por defecto
DEFAULT_DATABASE = {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'consul',
    'USER': 'postgres',
    'PASSWORD': 'Tec123',
    'HOST': 'localhost',
    'PORT': '5432',
}

# Si Render proporciona DATABASE_URL, úsala
DATABASES = {
    'default': dj_database_url.config(
        default=f"postgres://{DEFAULT_DATABASE['USER']}:{DEFAULT_DATABASE['PASSWORD']}@{DEFAULT_DATABASE['HOST']}/{DEFAULT_DATABASE['NAME']}",
        conn_max_age=600,
        ssl_require=os.getenv("RENDER", None) == "true",
    )
}


# ============================================================
# 🔐 PASSWORD VALIDATORS
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ============================================================
# 🌎 INTERNACIONALIZACIÓN
# ============================================================

LANGUAGE_CODE = 'es'

TIME_ZONE = 'America/Mexico_City'
USE_I18N = USE_L10N = USE_TZ = True


# ============================================================
# 📁 ARCHIVOS ESTÁTICOS (STATICFILES)
# ============================================================

STATIC_URL = '/static/'

# Archivos estáticos locales
STATICFILES_DIRS = [BASE_DIR / "static"]

# Carpeta para producción (Render)
STATIC_ROOT = BASE_DIR / "staticfiles"

# Para servir CSS/JS correctamente en Render
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


# ============================================================
# ⚙️ MODELOS Y SESIONES
# ============================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'citas.CustomUser'

LOGIN_URL = '/login/'   

# Sesiones largas
SESSION_COOKIE_AGE = 10 * 365 * 24 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
