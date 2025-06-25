"""
Matrix Bridge Integration Views - Production Grade
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils import timezone
import asyncio
import logging

from messaging.models import Conversation, Message
from messaging.serializers import ConversationSerializer, MessageSerializer
from .services.matrix_bridge_service import matrix_service
from companies.models import Company, CompanySettings

logger = logging.getLogger(__name__)


class MatrixBridgeViewSet(viewsets.ViewSet):
    """ViewSet for Matrix bridge operations"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get Matrix bridge status"""
        try:
            homeserver = getattr(settings, 'MATRIX_HOMESERVER', 'http://localhost:8008')
            user_id = getattr(settings, 'MATRIX_USER_ID', '@nexus_bot:matrix.nexus.local')
            
            return Response({
                "matrix": {
                    "homeserver": homeserver,
                    "user_id": user_id,
                    "available": bool(getattr(settings, 'MATRIX_ACCESS_TOKEN', '')),
                    "bridges": {
                        "whatsapp": {"status": "configured", "platform": "WhatsApp"},
                        "telegram": {"status": "configured", "platform": "Telegram"}, 
                        "instagram": {"status": "configured", "platform": "Instagram"},
                        "facebook": {"status": "configured", "platform": "Facebook"},
                        "signal": {"status": "configured", "platform": "Signal"}
                    }
                }
            })
            
        except Exception as e:
            logger.error(f"Error checking Matrix bridge status: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def send_message(self, request):
        """Send message through Matrix bridge"""
        import json
        platform = request.data.get('platform')
        recipient = request.data.get('recipient')
        content = request.data.get('content')
        message_type = request.data.get('message_type', 'text')

        logger.debug(f"send_message called with platform={platform}, recipient={recipient}")

        if not all([platform, recipient, content]):
            return Response(
                {"error": "platform, recipient, and content are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            company_id_str = str(request.user.company.id)
            logger.debug(f"Company ID converted to string: {company_id_str}")
            
            # Send via Matrix bridge
            result = asyncio.run(
                matrix_service.send_message_via_bridge(
                    platform=platform,
                    external_id=recipient,
                    company_id=company_id_str,
                    content=content,
                    message_type=message_type
                )
            )
            
            logger.debug(f"Matrix bridge result: {result}")

            if result.get('status') == 'success':
                # Create message record
                conversation, created = Conversation.objects.get_or_create(
                    company=request.user.company,
                    external_id=recipient,
                    platform=platform,
                    defaults={
                        "participants": [{"id": recipient, "platform": platform}],
                        "status": "active"
                    }
                )
                
                logger.debug(f"Conversation created/retrieved: {conversation.id}")

                message = Message.objects.create(
                    conversation=conversation,
                    direction="outgoing",
                    message_type=message_type,
                    content=content,
                    sender_info={"user_id": str(request.user.id), "username": request.user.username},
                    metadata={
                        "matrix_event_id": result.get('message_id'),
                        "matrix_room_id": result.get('room_id')
                    },
                    timestamp=timezone.now(),
                    is_processed=True
                )
                
                logger.debug(f"Message created: {message.id}")

                response_data = {
                    "status": "success",
                    "message_id": str(message.id),
                    "matrix_event_id": result.get('message_id'),
                    "matrix_room_id": result.get('room_id'),
                    "conversation_id": str(conversation.id)
                }
                
                logger.debug(f"Response data prepared: {response_data}")
                
                # Test JSON serialization
                try:
                    json.dumps(response_data)
                    logger.debug("Response data JSON serialization successful")
                except Exception as json_error:
                    logger.error(f"JSON serialization failed: {json_error}")
                    logger.error(f"Problematic data: {response_data}")
                    raise

                return Response(response_data)
            else:
                return Response(
                    {"error": result.get('error', 'Failed to send message')},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            logger.error(f"Error sending Matrix bridge message: {e}")
            logger.error(f"Exception type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def conversations(self, request):
        """List Matrix bridge conversations"""
        try:
            # Get Django conversations 
            django_conversations = Conversation.objects.filter(
                company=request.user.company
            ).order_by('-updated_at')
            
            conversations = []
            for conv in django_conversations:
                conversations.append({
                    "id": str(conv.id),
                    "platform": conv.platform,
                    "external_id": conv.external_id,
                    "participants": conv.participants,
                    "status": conv.status,
                    "last_message_at": conv.updated_at.isoformat(),
                    "source": "matrix_bridge"
                })
            
            return Response({
                "conversations": conversations,
                "total": len(conversations)
            })
            
        except Exception as e:
            logger.error(f"Error listing Matrix conversations: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def initialize_bridges(self, request):
        """Initialize Matrix bridges for the company"""
        try:
            company = request.user.company
            
            # Initialize Matrix service
            asyncio.run(matrix_service.initialize())
            
            # Update company settings
            settings_obj, created = CompanySettings.objects.get_or_create(company=company)
            
            # Use webhook_events to store bridge configuration
            webhook_events = settings_obj.webhook_events or []
            if 'matrix_bridge_initialized' not in webhook_events:
                webhook_events.append('matrix_bridge_initialized')
            settings_obj.webhook_events = webhook_events
            settings_obj.save()
            
            return Response({
                "status": "success",
                "message": "Matrix bridges initialized successfully",
                "matrix_config": {
                    'homeserver': getattr(settings, 'MATRIX_HOMESERVER'),
                    'configured_at': timezone.now().isoformat()
                }
            })
            
        except Exception as e:
            logger.error(f"Error initializing Matrix bridges: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
