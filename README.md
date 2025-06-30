# Nexus Contact Center Backend

Django бэкенд для Nexus Contact Center с поддержкой WebSocket, Redis и Celery.

## Деплой на Railway

Railway предоставляет бесплатный уровень для тестирования приложений с автоматическим развертыванием из GitHub.

### Настройка деплоя на Railway

1. Зарегистрируйтесь на [Railway](https://railway.app)

2. Создайте новый проект:
   - Выберите "Deploy from GitHub repo"
   - Выберите репозиторий `EldarGGG/nexus_back`
   - Railway автоматически определит, что это Python-приложение

3. Добавьте необходимые сервисы:
   - PostgreSQL: нажмите "+ New" > "Database" > "PostgreSQL"
   - Redis: нажмите "+ New" > "Database" > "Redis"

4. Настройте переменные окружения для Django:
   - `DJANGO_SETTINGS_MODULE=nexus_back.railway_settings`
   - `SECRET_KEY=ваш_секретный_ключ`
   - `DATABASE_URL`: Railway автоматически добавит эту переменную
   - `REDIS_URL`: Railway автоматически добавит эту переменную
   - `CORS_ALLOWED_ORIGINS=https://nexus-contact-center.vercel.app,http://localhost:3000`
   - `DEBUG=False`

5. Дождитесь окончания деплоя и получите URL вашего API

6. Обновите URL API на фронтенде (переменная `NEXT_PUBLIC_API_URL` на Vercel)

## Локальное развертывание

### С использованием Docker

```bash
docker-compose up -d
```

### Без Docker

1. Создайте и активируйте виртуальное окружение
2. Установите зависимости: `pip install -r requirements.txt`
3. Запустите Redis и PostgreSQL (или используйте SQLite)
4. Настройте переменные окружения
5. Запустите миграции: `cd nexus_back && python manage.py migrate`
6. Запустите сервер: `cd nexus_back && daphne -b 0.0.0.0 -p 8000 nexus_back.asgi:application`
7. В отдельном терминале запустите Celery: `cd nexus_back && celery -A nexus_back worker -l info`
