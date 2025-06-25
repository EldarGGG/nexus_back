from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import redis
import logging

logger = logging.getLogger(__name__)


def health_check(request):
    """Basic health check endpoint"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'nexus-messaging-platform',
        'version': '1.0.0'
    })


def detailed_health_check(request):
    """Detailed health check with all services"""
    health_status = {
        'status': 'healthy',
        'timestamp': request.META.get('REQUEST_TIME', 'unknown'),
        'checks': {}
    }
    
    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        health_status['checks']['database'] = {'status': 'healthy'}
    except Exception as e:
        health_status['checks']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'unhealthy'
    
    # Redis check
    try:
        redis_client = redis.Redis(
            host=getattr(settings, 'REDIS_HOST', 'localhost'),
            port=getattr(settings, 'REDIS_PORT', 6379),
            db=0
        )
        redis_client.ping()
        health_status['checks']['redis'] = {'status': 'healthy'}
    except Exception as e:
        health_status['checks']['redis'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'unhealthy'
    
    # Cache check
    try:
        cache.set('health_check_test', 'test_value', 30)
        test_value = cache.get('health_check_test')
        if test_value == 'test_value':
            health_status['checks']['cache'] = {'status': 'healthy'}
        else:
            health_status['checks']['cache'] = {
                'status': 'unhealthy',
                'error': 'Cache value mismatch'
            }
            health_status['status'] = 'unhealthy'
    except Exception as e:
        health_status['checks']['cache'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        health_status['status'] = 'unhealthy'
    
    return JsonResponse(health_status)
