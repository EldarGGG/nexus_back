"""
Instagram Messaging API integration service
"""
import requests
import logging
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any, Optional
from ..models import Conversation, Message
from companies.models import Company

logger = logging.getLogger(__name__)


class InstagramService:
    """Service for Instagram Messaging API integration"""

    def __init__(self):
        self.access_token = getattr(settings, 'INSTAGRAM_ACCESS_TOKEN', '')
        self.api_url = "https://graph.facebook.com/v17.0"

    def send_message(self, recipient_id: str, message: str, company_id: str, 
                    message_type: str = 'text', media_url: Optional[str] = None,
                    attachment_url: Optional[str] = None) -> Dict[str, Any]:
        """Send a message via Instagram Messaging API"""
        try:
            # Support both media_url and attachment_url for compatibility
            media_url = media_url or attachment_url
            
            page_id = self._get_page_id(company_id)
            
            payload = {
                "recipient": {"id": recipient_id},
                "message": {}
            }
            
            if message_type == 'text':
                payload["message"]["text"] = message
            elif message_type == 'image' and media_url:
                payload["message"]["attachment"] = {
                    "type": "image",
                    "payload": {"url": media_url}
                }
            elif message_type == 'file' and media_url:
                payload["message"]["attachment"] = {
                    "type": "file",
                    "payload": {"url": media_url}
                }
            
            response = requests.post(
                f"{self.api_url}/{page_id}/messages",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Instagram message sent successfully: {result}")
                return {
                    "status": "sent",
                    "message_id": result.get("message_id", ""),
                    **result
                }
            else:
                logger.error(f"Instagram API error: {response.text}")
                return {
                    "status": "failed",
                    "error": response.text
                }
                
        except Exception as e:
            logger.error(f"Error sending Instagram message: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

    def send_quick_reply(self, recipient_id: str, message: str, 
                        quick_replies: list, company_id: str) -> Dict[str, Any]:
        """Send a message with quick reply buttons"""
        try:
            page_id = self._get_page_id(company_id)
            
            payload = {
                "recipient": {"id": recipient_id},
                "message": {
                    "text": message,
                    "quick_replies": quick_replies
                }
            }
            
            response = requests.post(
                f"{self.api_url}/{page_id}/messages",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            return response.json()
                
        except Exception as e:
            logger.error(f"Error sending Instagram quick reply: {str(e)}")
            return {"status": "failed", "error": str(e)}

    def register_webhook(self, webhook_url: str, verify_token: str) -> Dict[str, Any]:
        """Register webhook for receiving Instagram messages"""
        try:
            # This would typically be done through Facebook Developer Console
            logger.info(f"Registering Instagram webhook: {webhook_url}")
            return {
                "status": "success",
                "webhook_url": webhook_url,
                "verify_token": verify_token
            }
        except Exception as e:
            logger.error(f"Error registering Instagram webhook: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

    def process_webhook(self, webhook_data: Dict[str, Any], company_id: str) -> Dict[str, Any]:
        """Process incoming Instagram webhook data"""
        try:
            company = Company.objects.get(id=company_id)
            
            for entry in webhook_data.get("entry", []):
                messaging_events = entry.get("messaging", [])
                
                for event in messaging_events:
                    if "message" in event:
                        self._process_incoming_message(event, company)
                    elif "postback" in event:
                        self._process_postback(event, company)
            
            return {"status": "processed"}
            
        except Exception as e:
            logger.error(f"Error processing Instagram webhook: {str(e)}")
            return {"status": "failed", "error": str(e)}

    def _process_incoming_message(self, event_data: Dict[str, Any], company: Company):
        """Process a single incoming message"""
        from datetime import datetime
        
        sender_id = event_data["sender"]["id"]
        recipient_id = event_data["recipient"]["id"]
        timestamp = datetime.fromtimestamp(event_data["timestamp"] / 1000)
        
        # Get sender info (would typically fetch from Instagram API)
        sender_info = {
            "id": sender_id,
            "platform_type": "instagram"
        }
        
        # Get or create conversation
        conversation, created = Conversation.objects.get_or_create(
            company=company,
            external_id=sender_id,
            platform="instagram",
            defaults={
                "participants": [sender_info],
                "status": "active"
            }
        )
        
        # Extract message content
        message_data = event_data.get("message", {})
        content = ""
        message_type = "text"
        attachments = []
        
        if "text" in message_data:
            content = message_data["text"]
        elif "attachments" in message_data:
            attachment = message_data["attachments"][0]
            attachment_type = attachment["type"]
            
            if attachment_type == "image":
                message_type = "image"
                content = "Image received"
                attachments.append({
                    "type": "image",
                    "url": attachment["payload"]["url"]
                })
            elif attachment_type == "video":
                message_type = "video"
                content = "Video received"
                attachments.append({
                    "type": "video",
                    "url": attachment["payload"]["url"]
                })
            elif attachment_type == "audio":
                message_type = "audio"
                content = "Audio received"
                attachments.append({
                    "type": "audio",
                    "url": attachment["payload"]["url"]
                })
        
        # Create message
        message = Message.objects.create(
            conversation=conversation,
            direction="incoming",
            message_type=message_type,
            content=content,
            sender_info=sender_info,
            attachments=attachments,
            metadata={"instagram_mid": message_data.get("mid")},
            timestamp=timestamp,
            is_processed=True  # Mark as processed since we're handling it here
        )
        
        logger.info(f"Instagram message processed: {message_data.get('mid', 'unknown')}")

    def _process_postback(self, event_data: Dict[str, Any], company: Company):
        """Process Instagram postback (button press)"""
        # Handle postback events from buttons
        logger.info(f"Instagram postback received: {event_data}")
        # Implementation would depend on your bot's button functionality

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile information"""
        try:
            response = requests.get(
                f"{self.api_url}/{user_id}",
                params={
                    "fields": "name,profile_pic",
                    "access_token": self.access_token
                }
            )
            
            if response.status_code == 200:
                return response.json()
            return None
                
        except Exception as e:
            logger.error(f"Error getting Instagram user profile: {str(e)}")
            return None

    def _get_page_id(self, company_id: str) -> str:
        """Get Instagram page ID for company"""
        # This would retrieve the page ID from company settings
        return getattr(settings, 'INSTAGRAM_PAGE_ID', '123456789')

    def create_conversation_and_message(self, user_id: str, message_content: str, 
                                      company: Company) -> Message:
        """Create conversation and message for testing"""
        conversation, _ = Conversation.objects.get_or_create(
            company=company,
            external_id=user_id,
            platform="instagram",
            defaults={"participants": [{"id": user_id}]}
        )
        
        return Message.objects.create(
            conversation=conversation,
            direction="incoming",
            content=message_content,
            sender_info={"id": user_id},
            timestamp=timezone.now()
        )
