from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BridgeConnectionViewSet, whatsapp_webhook, telegram_webhook
from .matrix_views import MatrixBridgeViewSet

router = DefaultRouter()
router.register('bridges', BridgeConnectionViewSet, basename='bridges')
router.register('matrix', MatrixBridgeViewSet, basename='matrix')

urlpatterns = [
    path('', include(router.urls)),
    
    # Webhook endpoints
    path('webhooks/whatsapp/<str:bridge_key>/', whatsapp_webhook, name='whatsapp_webhook'),
    path('webhooks/telegram/<str:bridge_key>/', telegram_webhook, name='telegram_webhook'),
]