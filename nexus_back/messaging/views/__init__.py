# Инициализация пакета views для приложения messaging

# Импорт ViewSet классов для регистрации в роутере
from .conversation_views import ConversationViewSet
from .message_views import MessageViewSet
from .template_views import MessageTemplateViewSet
from .bridge_views import BridgeManagementViewSet
