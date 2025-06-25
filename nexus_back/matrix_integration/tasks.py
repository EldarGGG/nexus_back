from celery import shared_task
from django.utils import timezone
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import BridgeConnection, BridgeMessage, AIAssistantConfig
from .services.ai_service import ai_service
from .services.bridge_manager import bridge_manager
import logging

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


@shared_task
def update_bridge_status():
    """Update status of all bridge connections"""
    try:
        bridges = BridgeConnection.objects.filter(status='connected')
        updated_count = 0
        
        for bridge in bridges:
            # Check if bridge is still active
            if bridge.bridge_key in bridge_manager.active_bridges:
                bridge.last_activity = timezone.now()
                bridge.save(update_fields=['last_activity'])
                updated_count += 1
            else:
                bridge.status = 'disconnected'
                bridge.save(update_fields=['status'])
                
                # Notify company group about bridge status change
                async_to_sync(channel_layer.group_send)(
                    f"company_{bridge.company.id}",
                    {
                        "type": "bridge_status_update",
                        "bridge_id": str(bridge.id),
                        "status": "disconnected",
                        "timestamp": timezone.now().isoformat()
                    }
                )
        
        logger.info(f"Updated status for {updated_count} bridges")
        return f"Updated status for {updated_count} bridges"
        
    except Exception as e:
        logger.error(f"Error updating bridge status: {str(e)}")
        raise


@shared_task
def process_pending_ai_requests():
    """Process pending AI requests"""
    try:
        # Get unprocessed messages that need AI responses
        pending_messages = BridgeMessage.objects.filter(
            ai_processed=False,
            direction='inbound',
            created_at__gte=timezone.now() - timezone.timedelta(hours=1)
        )
        
        processed_count = 0
        
        for message in pending_messages:
            try:
                # Get AI config for this bridge
                ai_config = AIAssistantConfig.objects.filter(
                    company=message.bridge.company,
                    bridge=message.bridge
                ).first()
                
                if not ai_config or not ai_config.auto_respond:
                    continue
                
                # Generate AI response
                ai_response = ai_service.generate_response(
                    message.content,
                    ai_config.system_prompt,
                    ai_config.model_name,
                    ai_config.temperature,
                    ai_config.max_tokens
                )
                
                if ai_response and ai_response.get('confidence', 0) >= ai_config.confidence_threshold:
                    message.ai_processed = True
                    message.ai_response = ai_response['content']
                    message.ai_confidence = ai_response.get('confidence', 0)
                    message.save()
                    
                    # Send AI response if auto-respond is enabled
                    if ai_config.auto_respond:
                        # TODO: Send response through bridge
                        pass
                    
                    # Notify company group
                    async_to_sync(channel_layer.group_send)(
                        f"company_{message.bridge.company.id}",
                        {
                            "type": "ai_response_generated",
                            "message_id": str(message.id),
                            "response": ai_response['content'],
                            "confidence": ai_response.get('confidence', 0),
                            "timestamp": timezone.now().isoformat()
                        }
                    )
                    
                    processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing AI request for message {message.id}: {str(e)}")
                continue
        
        logger.info(f"Processed {processed_count} AI requests")
        return f"Processed {processed_count} AI requests"
        
    except Exception as e:
        logger.error(f"Error processing pending AI requests: {str(e)}")
        raise


@shared_task
def send_message_through_bridge(bridge_key, customer_id, content, sender_name=None):
    """Send message through bridge asynchronously"""
    try:
        result = bridge_manager.send_manual_message(
            bridge_key, customer_id, content, sender_name
        )
        
        logger.info(f"Message sent through bridge {bridge_key} to {customer_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error sending message through bridge {bridge_key}: {str(e)}")
        raise


@shared_task
def process_incoming_webhook(platform, bridge_key, webhook_data):
    """Process incoming webhook data asynchronously"""
    try:
        result = bridge_manager.process_incoming_message(
            platform, bridge_key, webhook_data
        )
        
        logger.info(f"Processed incoming webhook for {platform} bridge {bridge_key}")
        return result
        
    except Exception as e:
        logger.error(f"Error processing webhook for {platform} bridge {bridge_key}: {str(e)}")
        raise


@shared_task
def cleanup_old_messages():
    """Clean up old messages based on company retention settings"""
    try:
        # Get all companies with their settings
        from companies.models import CompanySettings
        
        cleaned_count = 0
        
        for settings_obj in CompanySettings.objects.all():
            if settings_obj.message_retention_days > 0:
                cutoff_date = timezone.now() - timezone.timedelta(
                    days=settings_obj.message_retention_days
                )
                
                old_messages = BridgeMessage.objects.filter(
                    bridge__company=settings_obj.company,
                    created_at__lt=cutoff_date
                )
                
                count = old_messages.count()
                old_messages.delete()
                cleaned_count += count
                
                logger.info(f"Cleaned up {count} old messages for {settings_obj.company.name}")
        
        logger.info(f"Total cleaned up {cleaned_count} old messages")
        return f"Cleaned up {cleaned_count} old messages"
        
    except Exception as e:
        logger.error(f"Error cleaning up old messages: {str(e)}")
        raise


@shared_task
def initialize_bridge_connection(bridge_id):
    """Initialize bridge connection asynchronously"""
    try:
        bridge = BridgeConnection.objects.get(id=bridge_id)
        
        # Initialize the bridge
        result = bridge_manager.initialize_bridge(bridge)
        
        if result:
            bridge.status = 'connected'
            bridge.last_connected = timezone.now()
        else:
            bridge.status = 'error'
            bridge.error_message = "Failed to initialize bridge"
        
        bridge.save()
        
        # Notify company group
        async_to_sync(channel_layer.group_send)(
            f"company_{bridge.company.id}",
            {
                "type": "bridge_status_update",
                "bridge_id": str(bridge.id),
                "status": bridge.status,
                "timestamp": timezone.now().isoformat()
            }
        )
        
        logger.info(f"Bridge {bridge.bridge_key} initialization result: {bridge.status}")
        return f"Bridge {bridge.bridge_key} status: {bridge.status}"
        
    except BridgeConnection.DoesNotExist:
        logger.error(f"Bridge {bridge_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error initializing bridge {bridge_id}: {str(e)}")
        raise
