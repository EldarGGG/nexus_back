web: cd nexus_back && python manage.py migrate && daphne -b 0.0.0.0 -p $PORT nexus_back.asgi:application
worker: cd nexus_back && celery -A nexus_back worker -l info
