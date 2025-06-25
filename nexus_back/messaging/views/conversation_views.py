from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework import status

class ConversationViewSet(viewsets.ViewSet):
    """
    API для работы с беседами
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def list(self, request):
        # Заглушка для метода списка бесед
        return Response({"conversations": []})
        
    def retrieve(self, request, pk=None):
        # Заглушка для метода получения беседы
        return Response({"id": pk, "messages": []})
        
    def create(self, request):
        # Заглушка для метода создания беседы
        return Response({"id": "new-conversation-id"}, status=status.HTTP_201_CREATED)
