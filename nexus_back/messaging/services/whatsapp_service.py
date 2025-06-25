"""
WhatsApp Business API integration service
"""
import requests
import logging
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any, Optional
from ..models import Conversation, Message
from companies.models import Company

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service for WhatsApp Business API integration"""

    def __init__(self):
        self.api_url = getattr(settings, 'WHATSAPP_API_URL', 'https://graph.facebook.com/v17.0')
        self.access_token = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '')

    def send_message(self, phone_number: str, message: str, company_id: str, 
                    message_type: str = 'text', media_url: Optional[str] = None) -> Dict[str, Any]:
        """Send a message via WhatsApp Business API"""
        try:
            phone_number_id = self._get_phone_number_id(company_id)
            
            payload = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": message_type
            }
            
            if message_type == 'text':
                payload["text"] = {"body": message}
            elif message_type == 'image' and media_url:
                payload["image"] = {"link": media_url, "caption": message}
            elif message_type == 'document' and media_url:
                payload["document"] = {"link": media_url, "caption": message}
            
            response = requests.post(
                f"{self.api_url}/{phone_number_id}/messages",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"WhatsApp message sent successfully: {result}")
                return {
                    "message_id": result.get("messages", [{}])[0].get("id"),
                    "status": "sent",
                    "response": result
                }
            else:
                logger.error(f"WhatsApp API error: {response.text}")
                return {
                    "status": "failed",
                    "error": response.text
                }
                
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

    def register_webhook(self, webhook_url: str, verify_token: str) -> Dict[str, Any]:
        """Register webhook for receiving WhatsApp messages"""
        try:
            # This would typically involve setting up webhook through Meta Developer Console
            # For testing purposes, we'll simulate the response
            logger.info(f"Registering WhatsApp webhook: {webhook_url}")
            return {
                "status": "success",
                "webhook_url": webhook_url,
                "verify_token": verify_token
            }
        except Exception as e:
            logger.error(f"Error registering WhatsApp webhook: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

    def process_webhook(self, webhook_data: Dict[str, Any], company_id: str) -> Dict[str, Any]:
        """Process incoming WhatsApp webhook data"""
        try:
            # Validate webhook data structure
            if not webhook_data.get("entry"):
                raise ValueError("Invalid webhook data: missing 'entry' field")
                
            company = Company.objects.get(id=company_id)
            
            for entry in webhook_data.get("entry", []):
                for change in entry.get("changes", []):
                    messages = change.get("value", {}).get("messages", [])
                    
                    for message_data in messages:
                        self._process_incoming_message(message_data, company)
            
            return {"status": "processed"}
            
        except Exception as e:
            logger.error(f"Error processing WhatsApp webhook: {str(e)}")
            return {"status": "failed", "error": str(e)}

    def _process_incoming_message(self, message_data: Dict[str, Any], company: Company):
        """Process a single incoming message"""
        from datetime import datetime
        
        phone_number = message_data.get("from")
        message_id = message_data.get("id")
        timestamp = datetime.fromtimestamp(int(message_data.get("timestamp", 0)))
        
        # Get or create conversation
        conversation, created = Conversation.objects.get_or_create(
            company=company,
            external_id=phone_number,
            platform="whatsapp",
            defaults={
                "participants": [{"phone": phone_number}],
                "status": "active"
            }
        )
        
        # Extract message content
        content = ""
        message_type = "text"
        attachments = []
        
        if "text" in message_data:
            content = message_data["text"]["body"]
        elif "image" in message_data:
            message_type = "image"
            content = message_data["image"].get("caption", "Image received")
            attachments.append({
                "type": "image",
                "id": message_data["image"]["id"]
            })
        elif "document" in message_data:
            message_type = "document"
            content = message_data["document"].get("caption", "Document received")
            attachments.append({
                "type": "document",
                "id": message_data["document"]["id"]
            })
        
        # Create message
        message = Message.objects.create(
            conversation=conversation,
            direction="incoming",
            message_type=message_type,
            content=content,
            sender_info={"phone": phone_number},
            attachments=attachments,
            metadata={"whatsapp_message_id": message_id},
            timestamp=timestamp,
            is_processed=True  # Mark as processed since we're handling it here
        )
        
        logger.info(f"WhatsApp message processed: {message_id}")

    def _get_phone_number_id(self, company_id: str) -> str:
        """Get WhatsApp phone number ID for company"""
        # This would retrieve the phone number ID from company settings
        # For now, return a placeholder
        return getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '123456789')

    def create_conversation_and_message(self, phone_number: str, message_content: str, 
                                      company: Company) -> Message:
        """Create conversation and message for testing"""
        conversation, _ = Conversation.objects.get_or_create(
            company=company,
            external_id=phone_number,
            platform="whatsapp",
            defaults={"participants": [{"phone": phone_number}]}
        )
        
        return Message.objects.create(
            conversation=conversation,
            direction="incoming",
            content=message_content,
            sender_info={"phone": phone_number},
            timestamp=timezone.now()
        )
