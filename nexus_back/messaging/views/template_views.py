from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework import status

class MessageTemplateViewSet(viewsets.ViewSet):
    """
    API для работы с шаблонами сообщений
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def list(self, request):
        # Заглушка для метода списка шаблонов
        return Response({"templates": []})
        
    def retrieve(self, request, pk=None):
        # Заглушка для метода получения шаблона
        return Response({"id": pk, "name": "Демо шаблон", "content": "Это текст шаблона сообщения"})
        
    def create(self, request):
        # Заглушка для метода создания шаблона
        return Response({"id": "new-template-id"}, status=status.HTTP_201_CREATED)
