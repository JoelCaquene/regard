"""
Django settings for regard project.
"""

from pathlib import Path
import os
import dj_database_url
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

# Adiciona o hostname do Render dinamicamente
# O Render define esta variável em produção.
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')

# Configurações de Hosts Permitidos
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # WhiteNoise para servir arquivos estáticos de forma eficiente
    'whitenoise.runserver_nostatic',
    
    # Seus Apps
    'core',
    # Outros apps do projeto (se houver)
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise deve vir logo abaixo do SecurityMiddleware
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'regard.urls'

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

WSGI_APPLICATION = 'regard.wsgi.application'


# 🚀 Configuração do Banco de Dados para Produção (Render/PostgreSQL)
# Se estiver em produção (não DEBUG) e a DATABASE_URL for fornecida, use PostgreSQL.
if not DEBUG and 'DATABASE_URL' in os.environ:
    DATABASES = {
        'default': dj_database_url.config(
            conn_max_age=600,
            ssl_require=True  # Essencial para o PostgreSQL do Render
        )
    }
    # Configura o Django para reconhecer a conexão SSL através do proxy do Render
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    # Configuração local (desenvolvimento)
    DATABASES = {
        'default': dj_database_url.config(
            default=f'sqlite:///{BASE_DIR}/db.sqlite3'
        )
    }


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
LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'Africa/Luanda'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles' # Onde os arquivos estáticos serão coletados
STATICFILES_DIRS = [BASE_DIR / 'static'] # Seus diretórios estáticos locais

# ======================================================================
# 🚀 CORREÇÃO CRÍTICA PARA ARQUIVOS ESTÁTICOS NO DJANGO 5 / RENDER
# Usamos STORAGES em vez de STATICFILES_STORAGE
# ======================================================================

# REMOVIDA: STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ======================================================================
# CONFIGURAÇÕES DE ARMAZENAMENTO DE ARQUIVOS (MEDIA FILES)
# CLOUDINARY FOI REMOVIDO
# ======================================================================

# Configurações para arquivos de mídia (ARMAZENAMENTO LOCAL em Desenvolvimento)
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# Se você precisar de armazenamento de mídia em produção, precisará 
# adicionar django-storages e configurar o AWS S3 (ou outro) aqui.
# ======================================================================
# FIM DA CONFIGURAÇÃO DE ARMAZENAMENTO
# ======================================================================


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# UKZ o modelo de usuário personalizado
AUTH_USER_MODEL = 'core.CustomUser'

LOGIN_URL = 'login'

# Configuração de segurança adicional para produção
if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000 # 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    