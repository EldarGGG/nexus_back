"""
Настройки специально для деплоя на Railway
"""
import os
import dj_database_url
from .settings import *

# Настройка безопасности
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
SECRET_KEY = os.environ.get('SECRET_KEY', SECRET_KEY)

# Настройка хостов
ALLOWED_HOSTS = ['*']  # В продакшене лучше указать конкретные домены
CSRF_TRUSTED_ORIGINS = ['https://*.up.railway.app']

# Настройка статических файлов
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Настройка медиа-файлов
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Добавляем whitenoise middleware
if 'whitenoise.middleware.WhiteNoiseMiddleware' not in MIDDLEWARE:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Настройка базы данных через переменные окружения
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL)
    }

# Настройка Redis через переменные окружения
REDIS_URL = os.environ.get('REDIS_URL')
if REDIS_URL:
    # Настройка кэша
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient"
            }
        }
    }
    
    # Настройка каналов
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
            },
        },
    }
    
    # Настройка Celery
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

# Настройка CORS
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS.extend([
    "https://nexus-contact-center.vercel.app",
    "http://localhost:3000"
])
