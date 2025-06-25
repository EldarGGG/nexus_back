from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework import status

class MessageViewSet(viewsets.ViewSet):
    """
    API для работы с сообщениями
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def list(self, request):
        # Заглушка для метода списка сообщений
        return Response({"messages": []})
        
    def retrieve(self, request, pk=None):
        # Заглушка для метода получения сообщения
        return Response({"id": pk, "content": "Демо сообщение", "timestamp": "2025-06-25T12:00:00Z"})
        
    def create(self, request):
        # Заглушка для метода создания сообщения
        return Response({"id": "new-message-id"}, status=status.HTTP_201_CREATED)
