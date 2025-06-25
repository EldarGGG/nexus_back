from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from .models import BridgeConnection, BridgeCredentials, BridgeMessage, AIAssistantConfig
from .serializers import (
    BridgeConnectionSerializer, WhatsAppConnectionSerializer, TelegramConnectionSerializer,
    BridgeMessageSerializer, AIAssistantConfigSerializer, SendMessageSerializer
)
from .services.bridge_manager import bridge_manager
from .services.matrix_service import matrix_service
import asyncio
import logging

logger = logging.getLogger(__name__)

class BridgeConnectionViewSet(viewsets.ModelViewSet):
    serializer_class = BridgeConnectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BridgeConnection.objects.filter(company=self.request.user.company)

    @action(detail=False, methods=['post'])
    def connect_whatsapp(self, request):
        """Connect WhatsApp Business API"""
        serializer = WhatsAppConnectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create bridge connection
        bridge = BridgeConnection.objects.create(
            company=request.user.company,
            platform='whatsapp',
            name=serializer.validated_data['name'],
            status='pending'
        )
        
        # Store encrypted credentials
        credentials_data = {
            'phone_number_id': serializer.validated_data['phone_number_id'],
            'access_token': serializer.validated_data['access_token']
        }
        
        bridge_credentials = BridgeCredentials.objects.create(bridge=bridge)
        bridge_credentials.encrypt_credentials(credentials_data)
        bridge_credentials.save()
        
        # Initialize bridge asynchronously
        asyncio.create_task(bridge_manager.initialize_bridge(bridge))
        
        return Response({
            'message': 'WhatsApp connection initiated',
            'bridge_id': bridge.id,
            'bridge_key': bridge.bridge_key
        })

    @action(detail=False, methods=['post'])
    def connect_telegram(self, request):
        """Connect Telegram Bot"""
        serializer = TelegramConnectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create bridge connection
        bridge = BridgeConnection.objects.create(
            company=request.user.company,
            platform='telegram',
            name=serializer.validated_data['name'],
            status='pending'
        )
        
        # Store encrypted credentials
        credentials_data = {
            'bot_token': serializer.validated_data['bot_token']
        }
        
        bridge_credentials = BridgeCredentials.objects.create(bridge=bridge)
        bridge_credentials.encrypt_credentials(credentials_data)
        bridge_credentials.save()
        
        # Initialize bridge asynchronously
        asyncio.create_task(bridge_manager.initialize_bridge(bridge))
        
        return Response({
            'message': 'Telegram connection initiated',
            'bridge_id': bridge.id,
            'bridge_key': bridge.bridge_key
        })

    @action(detail=True, methods=['post'])
    def disconnect(self, request, pk=None):
        """Disconnect a bridge"""
        bridge = self.get_object()
        bridge.status = 'disconnected'
        bridge.save()
        
        # Remove from active bridges
        if bridge.bridge_key in bridge_manager.active_bridges:
            del bridge_manager.active_bridges[bridge.bridge_key]
        
        return Response({'message': 'Bridge disconnected'})

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Get messages for a bridge"""
        bridge = self.get_object()
        messages = BridgeMessage.objects.filter(bridge=bridge).order_by('-created_at')[:50]
        serializer = BridgeMessageSerializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send message through bridge"""
        bridge = self.get_object()
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Send message asynchronously
            result = asyncio.run(bridge_manager.send_manual_message(
                bridge.bridge_key,
                serializer.validated_data['customer_id'],
                serializer.validated_data['content'],
                request.user.get_full_name() or request.user.username
            ))
            
            return Response({
                'message': 'Message sent successfully',
                'result': result
            })
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def ai_config(self, request, pk=None):
        """Get or update AI configuration for bridge"""
        bridge = self.get_object()
        
        if request.method == 'GET':
            try:
                ai_config = AIAssistantConfig.objects.get(bridge=bridge)
                serializer = AIAssistantConfigSerializer(ai_config)
                return Response(serializer.data)
            except AIAssistantConfig.DoesNotExist:
                return Response({'message': 'No AI config found'}, 
                              status=status.HTTP_404_NOT_FOUND)
        
        elif request.method == 'POST':
            serializer = AIAssistantConfigSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            ai_config, created = AIAssistantConfig.objects.update_or_create(
                company=bridge.company,
                bridge=bridge,
                defaults=serializer.validated_data
            )
            
            return Response({
                'message': 'AI configuration updated',
                'config': AIAssistantConfigSerializer(ai_config).data
            })

# Webhook handlers
@api_view(['POST', 'GET'])
@permission_classes([AllowAny])
def whatsapp_webhook(request, bridge_key):
    """Handle WhatsApp webhooks for specific bridge"""
    
    if request.method == 'GET':
        # Webhook verification
        if request.GET.get('hub.verify_token') == settings.WHATSAPP_VERIFY_TOKEN:
            return Response(request.GET.get('hub.challenge'))
        return Response('Invalid verify token', status=400)
    
    # Process incoming message
    try:
        bridge = BridgeConnection.objects.get(bridge_key=bridge_key, platform='whatsapp')
        if bridge.status != 'connected':
            return Response('Bridge not active', status=400)
        
        # Process async
        asyncio.create_task(
            bridge_manager.process_incoming_message('whatsapp', bridge_key, request.data)
        )
        
        return Response({'status': 'success'})
        
    except BridgeConnection.DoesNotExist:
        logger.error(f"Bridge not found: {bridge_key}")
        return Response('Bridge not found', status=404)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def telegram_webhook(request, bridge_key):
    """Handle Telegram webhooks for specific bridge"""
    try:
        bridge = BridgeConnection.objects.get(bridge_key=bridge_key, platform='telegram')
        
        asyncio.create_task(
            bridge_manager.process_incoming_message('telegram', bridge_key, request.data)
        )
        
        return Response({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
        return Response({'error': str(e)}, status=500)