"""
ПУЛЬСАР — настройки Django-бэкенда (скелет).
Данные (в т.ч. персональные из заявок) — в РФ по 152-ФЗ:
Postgres размещается на российском облаке/хостинге (Yandex Cloud / Timeweb / Selectel).
"""
import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', 'dev-insecure-change-me')
DEBUG = os.getenv('DEBUG', '1') == '1'
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'booking',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

# БД: DATABASE_URL (Postgres в РФ) или локальный SQLite для разработки
_db_url = os.getenv('DATABASE_URL', '').strip()
if _db_url:
    DATABASES = {'default': dj_database_url.parse(_db_url, conn_max_age=600)}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    # отсекает «123456», «qwerty» и прочие пароли из списков утечек
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
]

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'   # подтверждающие документы по показателям
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------- ИИ-подбор позиций по описанию задачи ----------
# YandexGPT. Ключ и каталог берём из окружения; если их нет, подбор работает
# на локальном алгоритме — сайт не ломается от отсутствия внешнего сервиса.
YANDEX_API_KEY = os.getenv('YANDEX_API_KEY', '').strip()
YANDEX_FOLDER_ID = os.getenv('YANDEX_FOLDER_ID', '').strip()
YANDEX_MODEL = os.getenv('YANDEX_MODEL', 'yandexgpt-lite/latest')
YANDEX_LLM_URL = os.getenv(
    'YANDEX_LLM_URL', 'https://llm.api.cloud.yandex.net/foundationModels/v1/completion')
# Ждать модель дольше нескольких секунд бессмысленно: пользователь уйдёт,
# а локальный подбор ответит мгновенно.
ASSIST_TIMEOUT = float(os.getenv('ASSIST_TIMEOUT', '8'))

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    # ИИ-подбор доступен без входа, а каждый запрос к модели платный —
    # ограничиваем частоту, чтобы счёт не зависел от случайного бота.
    'DEFAULT_THROTTLE_RATES': {'assist': os.getenv('ASSIST_RATE', '20/min')},
}

# CORS: фронт (личный кабинет) обращается к API. Токен-авторизация не зависит от cookie.
CORS_ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:4177,http://localhost:8080,http://127.0.0.1:8080,'
    'http://localhost:5500,http://127.0.0.1:5500,https://pulsar.zimermans.ru').split(',') if o.strip()]
# В разработке удобно разрешить любой источник (данные защищены токеном, не cookie).
CORS_ALLOW_ALL_ORIGINS = DEBUG
# Доверенные источники для CSRF (нужно для входа в /admin по HTTPS).
# Берём и из CORS-списка, и — на всякий — из ALLOWED_HOSTS как https://<host>,
# чтобы при фронте на том же домене (CORS может быть пустым) логин оператора
# в кабинет не упирался в проверку CSRF.
CSRF_TRUSTED_ORIGINS = list({
    o for o in CORS_ALLOWED_ORIGINS if o.startswith('http')
} | {
    'https://' + h for h in ALLOWED_HOSTS
    if h not in ('localhost', '127.0.0.1', '*') and not h.startswith('.')
})
