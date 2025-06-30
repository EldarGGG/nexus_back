web: daphne -b 0.0.0.0 -p $PORT nexus_back.asgi:application
worker: celery -A nexus_back worker -l info
