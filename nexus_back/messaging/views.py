from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils import timezone
import logging

from .models import Conversation, Message, MessageTemplate
from .serializers import ConversationSerializer, MessageSerializer, MessageTemplateSerializer
from .services.whatsapp_service import WhatsAppService
from .services.telegram_service import TelegramService
from .services.instagram_service import InstagramService
from .services.ai_service import AIService
from companies.models import Company, CompanySettings

logger = logging.getLogger(__name__)


class ConversationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing conversations"""
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Conversation.objects.filter(company=self.request.user.company)
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Get messages for a conversation"""
        conversation = self.get_object()
        messages = Message.objects.filter(conversation=conversation).order_by('created_at')
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send a message in this conversation"""
        conversation = self.get_object()
        serializer = MessageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(conversation=conversation, sender=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign conversation to an agent"""
        conversation = self.get_object()
        agent_id = request.data.get('agent_id')
        if agent_id:
            conversation.assigned_to_id = agent_id
            conversation.save()
            return Response({'status': 'assigned'})
        return Response({'error': 'agent_id required'}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def send_template_message(self, request, pk=None):
        """Send a templated message"""
        conversation = self.get_object()
        template_id = request.data.get('template_id')
        variables = request.data.get('variables', {})
        
        if template_id:
            template = get_object_or_404(MessageTemplate, id=template_id, company=request.user.company)
            content = template.render(variables)
            
            message = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=content,
                direction='outgoing'
            )
            serializer = MessageSerializer(message)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response({'error': 'template_id required'}, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        """Set company when creating conversation"""
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['post'])
    def send_message(self, request):
        """Send a message through the appropriate bridge"""
        platform = request.data.get('platform')
        recipient = request.data.get('recipient')
        content = request.data.get('content')
        message_type = request.data.get('message_type', 'text')
        attachment_url = request.data.get('attachment_url')

        if not all([platform, recipient, content]):
            return Response(
                {"error": "platform, recipient, and content are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get or create conversation
            conversation, created = Conversation.objects.get_or_create(
                company=request.user.company,
                external_id=recipient,
                platform=platform,
                defaults={
                    "participants": [{"id": recipient, "platform": platform}],
                    "status": "active"
                }
            )

            # Send message through appropriate service
            result = self._send_platform_message(
                platform, recipient, content, message_type, attachment_url, request.user.company
            )

            if result.get('status') == 'success':
                # Create message record
                message = Message.objects.create(
                    conversation=conversation,
                    direction="outgoing",
                    message_type=message_type,
                    content=content,
                    sender_info={"user_id": request.user.id, "username": request.user.username},
                    metadata=result.get('metadata', {}),
                    is_processed=True
                )

                return Response({
                    "status": "success",
                    "message_id": message.id,
                    "platform_message_id": result.get('message_id'),
                    "conversation_id": conversation.id
                })
            else:
                return Response(
                    {"error": result.get('error', 'Failed to send message')},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _send_platform_message(self, platform, recipient, content, message_type, attachment_url, company):
        """Send message through the appropriate platform service"""
        if platform == 'whatsapp':
            service = WhatsAppService()
            if message_type == 'text':
                return service.send_text_message(recipient, content, str(company.id))
            elif message_type == 'image' and attachment_url:
                return service.send_image_message(recipient, attachment_url, content, str(company.id))
            elif message_type == 'document' and attachment_url:
                return service.send_document_message(recipient, attachment_url, content, str(company.id))

        elif platform == 'telegram':
            service = TelegramService()
            if message_type == 'text':
                return service.send_message(recipient, content)
            elif message_type == 'image' and attachment_url:
                return service.send_photo(recipient, attachment_url, content)
            elif message_type == 'document' and attachment_url:
                return service.send_document(recipient, attachment_url, content)

        elif platform == 'instagram':
            service = InstagramService()
            if message_type == 'text':
                return service.send_message(recipient, content, str(company.id))
            elif message_type == 'image' and attachment_url:
                return service.send_image_message(recipient, attachment_url, content, str(company.id))

        return {"status": "failed", "error": f"Unsupported platform or message type: {platform}/{message_type}"}


class MessageViewSet(viewsets.ModelViewSet):
    """ViewSet for managing messages"""
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter messages by user's company"""
        return Message.objects.filter(
            conversation__company=self.request.user.company
        ).select_related('conversation').order_by('-timestamp')

    @action(detail=True, methods=['post'])
    def generate_ai_response(self, request, pk=None):
        """Generate AI response for a message"""
        message = self.get_object()
        
        try:
            ai_service = AIService()
            
            # Build context from conversation history
            conversation_history = Message.objects.filter(
                conversation=message.conversation
            ).order_by('-timestamp')[:10]
            
            context = {
                "company": message.conversation.company.name,
                "platform": message.conversation.platform,
                "conversation_history": [
                    {
                        "direction": msg.direction,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat()
                    }
                    for msg in reversed(conversation_history)
                ]
            }
            
            # Generate response
            response = ai_service.generate_response(
                message.content,
                context=context,
                company_id=str(message.conversation.company.id)
            )
            
            return Response({
                "suggested_response": response.get("response", ""),
                "intent": response.get("intent"),
                "confidence": response.get("confidence"),
                "entities": response.get("entities", [])
            })
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MessageTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for managing message templates"""
    serializer_class = MessageTemplateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter templates by user's company"""
        return MessageTemplate.objects.filter(company=self.request.user.company)

    def perform_create(self, serializer):
        """Set company when creating template"""
        serializer.save(company=self.request.user.company)


class BridgeManagementViewSet(viewsets.ViewSet):
    """ViewSet for managing bridge configurations"""
    # Временно отключены требования авторизации для тестирования
    # permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get status of all bridges for the company"""
        company = request.user.company
        
        try:
            # Check WhatsApp status
            whatsapp_status = self._check_whatsapp_status(company)
            
            # Check Telegram status  
            telegram_status = self._check_telegram_status(company)
            
            # Check Instagram status
            instagram_status = self._check_instagram_status(company)
            
            # Check AI status
            ai_service = AIService()
            ai_status = {
                "available": ai_service.is_available(),
                "model_info": ai_service.get_model_info()
            }
            
            return Response({
                "whatsapp": whatsapp_status,
                "telegram": telegram_status, 
                "instagram": instagram_status,
                "ai": ai_status
            })
            
        except Exception as e:
            logger.error(f"Error checking bridge status: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def configure_whatsapp(self, request):
        """Configure WhatsApp bridge for company"""
        webhook_url = request.data.get('webhook_url')
        verify_token = request.data.get('verify_token')
        
        if not webhook_url:
            return Response(
                {"error": "webhook_url is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = WhatsAppService()
            result = service.register_webhook(webhook_url, verify_token)
            
            if result.get('status') == 'success':
                # Save configuration to company settings
                settings_obj, created = CompanySettings.objects.get_or_create(
                    company=request.user.company
                )
                webhook_settings = settings_obj.webhook_settings or {}
                webhook_settings['whatsapp'] = {
                    'webhook_url': webhook_url,
                    'verify_token': verify_token,
                    'configured_at': timezone.now().isoformat()
                }
                settings_obj.webhook_settings = webhook_settings
                settings_obj.save()
                
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error configuring WhatsApp: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def configure_telegram(self, request):
        """Configure Telegram bridge for company"""
        webhook_url = request.data.get('webhook_url')
        bot_token = request.data.get('bot_token')
        
        if not all([webhook_url, bot_token]):
            return Response(
                {"error": "webhook_url and bot_token are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            service = TelegramService()
            result = service.set_webhook(webhook_url)
            
            if result.get('status') == 'success':
                # Save configuration
                settings_obj, created = CompanySettings.objects.get_or_create(
                    company=request.user.company
                )
                webhook_settings = settings_obj.webhook_settings or {}
                webhook_settings['telegram'] = {
                    'webhook_url': webhook_url,
                    'bot_token': bot_token,
                    'configured_at': timezone.now().isoformat()
                }
                settings_obj.webhook_settings = webhook_settings
                settings_obj.save()
                
            return Response(result)
            
        except Exception as e:
            logger.error(f"Error configuring Telegram: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _check_whatsapp_status(self, company):
        """Check WhatsApp bridge status"""
        try:
            settings_obj = CompanySettings.objects.get(company=company)
            whatsapp_config = settings_obj.webhook_settings.get('whatsapp', {})
            
            return {
                "configured": bool(whatsapp_config.get('webhook_url')),
                "webhook_url": whatsapp_config.get('webhook_url'),
                "last_configured": whatsapp_config.get('configured_at'),
                "status": "active" if whatsapp_config.get('webhook_url') else "not_configured"
            }
        except CompanySettings.DoesNotExist:
            return {
                "configured": False,
                "status": "not_configured"
            }

    def _check_telegram_status(self, company):
        """Check Telegram bridge status"""
        try:
            settings_obj = CompanySettings.objects.get(company=company)
            telegram_config = settings_obj.webhook_settings.get('telegram', {})
            
            return {
                "configured": bool(telegram_config.get('webhook_url')),
                "webhook_url": telegram_config.get('webhook_url'),
                "last_configured": telegram_config.get('configured_at'),
                "status": "active" if telegram_config.get('webhook_url') else "not_configured"
            }
        except CompanySettings.DoesNotExist:
            return {
                "configured": False,
                "status": "not_configured"
            }

    def _check_instagram_status(self, company):
        """Check Instagram bridge status"""
        try:
            settings_obj = CompanySettings.objects.get(company=company)
            instagram_config = settings_obj.webhook_settings.get('instagram', {})
            
            return {
                "configured": bool(instagram_config.get('webhook_url')),
                "webhook_url": instagram_config.get('webhook_url'),
                "last_configured": instagram_config.get('configured_at'),
                "status": "active" if instagram_config.get('webhook_url') else "not_configured"
            }
        except CompanySettings.DoesNotExist:
            return {
                "configured": False,
                "status": "not_configured"
            }
