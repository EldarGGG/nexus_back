import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nexus_back.settings')

app = Celery('nexus_back')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
    'cleanup-expired-invitations': {
        'task': 'companies.tasks.cleanup_expired_invitations',
        'schedule': 3600.0,  # Every hour
    },
    'update-bridge-status': {
        'task': 'matrix_integration.tasks.update_bridge_status',
        'schedule': 300.0,  # Every 5 minutes
    },
    'process-ai-requests': {
        'task': 'matrix_integration.tasks.process_pending_ai_requests',
        'schedule': 60.0,  # Every minute
    },
    'cleanup-old-sessions': {
        'task': 'authentication.tasks.cleanup_old_sessions',
        'schedule': 86400.0,  # Daily
    },
}

app.conf.timezone = 'UTC'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
