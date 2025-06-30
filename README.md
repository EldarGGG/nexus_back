# Nexus Contact Center Backend

Django бэкенд для Nexus Contact Center.

## Деплой на Render

### Автоматический деплой через Blueprint

1. Войдите в аккаунт на [Render](https://render.com)
2. Перейдите в раздел Blueprints
3. Нажмите "New Blueprint Instance"
4. Выберите этот репозиторий
5. Следуйте инструкциям для настройки переменных окружения
6. Нажмите "Apply"

### Ручная настройка на Render

1. Войдите в свой аккаунт [Render](https://render.com)
2. Создайте новый Web Service:
   - Выберите ваш репозиторий
   - Выберите ветку `master`
   - Выберите тип `Python`
   - Укажите команду сборки: `pip install -r requirements.txt`
   - Укажите команду запуска: `daphne -b 0.0.0.0 -p $PORT nexus_back.asgi:application`

3. Создайте PostgreSQL базу данных:
   - В Dashboard выберите "New" > "PostgreSQL"
   - Укажите имя "nexus-db"
   - Выберите бесплатный план

4. Создайте Redis сервис:
   - В Dashboard выберите "New" > "Redis"
   - Укажите имя "nexus-redis"
   - Выберите бесплатный план

5. Настройте переменные окружения для Web Service:
   - `DJANGO_SETTINGS_MODULE=nexus_back.render_settings`
   - `DJANGO_SECRET_KEY=[сгенерированный_ключ]`
   - `DATABASE_URL=[URL_из_панели_PostgreSQL]`
   - `REDIS_URL=[URL_из_панели_Redis]`
   - `CELERY_BROKER_URL=[URL_из_панели_Redis]`
   - `CELERY_RESULT_BACKEND=[URL_из_панели_Redis]`
   - `CORS_ALLOWED_ORIGINS=https://nexus-contact-center.vercel.app,http://localhost:3000`

## Локальная разработка

1. Создайте и активируйте виртуальное окружение
2. Установите зависимости: `pip install -r requirements.txt`
3. Запустите миграции: `python manage.py migrate`
4. Запустите сервер: `python manage.py runserver`
5. Для WebSockets используйте: `daphne -b 0.0.0.0 -p 8000 nexus_back.asgi:application`
