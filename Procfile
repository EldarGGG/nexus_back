web: PYTHONPATH=. python nexus_back/manage.py migrate && python -m daphne -b 0.0.0.0 -p $PORT nexus_back.asgi:application
worker: PYTHONPATH=. celery -A nexus_back worker -l info
