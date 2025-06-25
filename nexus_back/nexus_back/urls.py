"""
Nexus Back - B2B AI SaaS Messaging Platform
URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Health Check
    path('health/', include('health_check.urls')),
    
    # API Endpoints
    path('api/auth/', include('authentication.urls')),
    path('api/', include('companies.urls')),
    path('api/matrix_integration/', include('matrix_integration.urls')),
    path('api/messaging/', include('messaging.urls')),
    path('api/campaigns/', include('campaigns.urls')),
    path('api/automation/', include('automation.urls')),
    path('api/analytics/', include('analytics.urls')),
    path('api/billing/', include('billing.urls')),
    path('api/integrations/', include('integrations.urls')),
    path('api/notifications/', include('notifications.urls')),
    
    # Proxy routes for frontend compatibility
    path('messaging/', include('messaging.urls')),  # Добавлен прокси-маршрут
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
