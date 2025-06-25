"""
Celery tasks for messaging services
"""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task
def process_incoming_message(platform, message_data, company_id):
    """Process incoming message asynchronously"""
    return process_incoming_message_task(platform, message_data, company_id)


@shared_task
def process_incoming_message_task(platform, message_data, company_id):
    """Process incoming message asynchronously"""
    try:
        if platform == 'whatsapp':
            from .services.whatsapp_service import WhatsAppService
            service = WhatsAppService()
            return service.process_webhook(message_data, company_id)
        elif platform == 'telegram':
            from .services.telegram_service import TelegramService
            service = TelegramService()
            return service.process_webhook(message_data, company_id)
        elif platform == 'instagram':
            from .services.instagram_service import InstagramService
            service = InstagramService()
            return service.process_webhook(message_data, company_id)
        else:
            logger.error(f"Unknown platform: {platform}")
            return {"status": "failed", "error": f"Unknown platform: {platform}"}
    except Exception as e:
        logger.error(f"Error processing {platform} message: {e}")
        return {"status": "failed", "error": str(e)}


@shared_task
def generate_ai_response_task(message_id):
    """Generate AI response for a message asynchronously"""
    try:
        from .models import Message
        from .services.ai_service import AIService
        
        message = Message.objects.get(id=message_id)
        conversation = message.conversation
        
        # Get conversation history
        history = list(Message.objects.filter(
            conversation=conversation
        ).order_by('-created_at')[:10].values('content', 'direction', 'created_at'))
        
        # Get company context
        company_context = {
            "name": conversation.company.name,
            "industry": conversation.company.industry,
        }
        
        ai_service = AIService()
        result = ai_service.generate_response(
            message=message.content,
            conversation_history=history,
            company_context=company_context
        )
        
        # Update message with AI response
        message.ai_response = result.get('response', '')
        message.ai_confidence = result.get('confidence', 0.0)
        message.ai_intent = result.get('intent', 'unknown')
        message.save()
        
        return result
        
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return {"status": "failed", "error": str(e)}


@shared_task
def send_message_task(platform, recipient, content, company_id, message_type='text'):
    """Send outbound message asynchronously"""
    try:
        if platform == 'whatsapp':
            from .services.whatsapp_service import WhatsAppService
            service = WhatsAppService()
            return service.send_message(
                phone_number=recipient,
                message=content,
                company_id=company_id,
                message_type=message_type
            )
        elif platform == 'telegram':
            from .services.telegram_service import TelegramService
            service = TelegramService()
            return service.send_message(
                chat_id=recipient,
                message=content,
                company_id=company_id
            )
        elif platform == 'instagram':
            from .services.instagram_service import InstagramService
            service = InstagramService()
            return service.send_message(
                recipient_id=recipient,
                message=content,
                company_id=company_id
            )
        else:
            logger.error(f"Unknown platform: {platform}")
            return {"status": "failed", "error": f"Unknown platform: {platform}"}
    except Exception as e:
        logger.error(f"Error sending {platform} message: {e}")
        return {"status": "failed", "error": str(e)}
