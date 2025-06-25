from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .webhook_views import WhatsAppWebhookView, TelegramWebhookView, InstagramWebhookView
from .views.telegram_webhook import telegram_webhook, telegram_ai_settings

app_name = 'messaging'

router = DefaultRouter()
router.register(r'conversations', views.ConversationViewSet, basename='conversation')
router.register(r'messages', views.MessageViewSet, basename='message')
router.register(r'templates', views.MessageTemplateViewSet, basename='messagetemplate')
router.register(r'bridges', views.BridgeManagementViewSet, basename='bridge')

urlpatterns = [
    path('', include(router.urls)),
    # Webhook endpoints
    path('webhooks/whatsapp/', WhatsAppWebhookView.as_view(), name='whatsapp-webhook'),
    path('webhooks/telegram/', TelegramWebhookView.as_view(), name='telegram-webhook'),
    path('webhooks/instagram/', InstagramWebhookView.as_view(), name='instagram-webhook'),
    
    # AI-powered Telegram webhook endpoints
    path('companies/<str:company_id>/telegram/webhook/', telegram_webhook, name='ai-telegram-webhook'),
    path('companies/<str:company_id>/telegram/ai-settings/', telegram_ai_settings, name='ai-telegram-settings'),
]
