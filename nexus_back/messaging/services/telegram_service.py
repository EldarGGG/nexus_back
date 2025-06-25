"""
Telegram Bot API integration service
"""
import requests
import logging
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any, Optional
from ..models import Conversation, Message
from companies.models import Company

logger = logging.getLogger(__name__)


class TelegramService:
    """Service for Telegram Bot API integration"""

    def __init__(self):
        self.bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(self, chat_id: str, message: str, company_id: str, 
                    message_type: str = 'text', **kwargs) -> Dict[str, Any]:
        """Send a message via Telegram Bot API"""
        try:
            payload = {
                "chat_id": chat_id,
                "text": message
            }
            
            # Add optional parameters
            if 'reply_markup' in kwargs:
                payload['reply_markup'] = kwargs['reply_markup']
            if 'parse_mode' in kwargs:
                payload['parse_mode'] = kwargs['parse_mode']
            
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Telegram message sent successfully: {result}")
                return result
            else:
                logger.error(f"Telegram API error: {response.text}")
                return {
                    "ok": False,
                    "error": response.text
                }
                
        except Exception as e:
            logger.error(f"Error sending Telegram message: {str(e)}")
            return {
                "ok": False,
                "error": str(e)
            }

    def send_photo(self, chat_id: str, photo_url: str, caption: str = "") -> Dict[str, Any]:
        """Send a photo via Telegram Bot API"""
        try:
            payload = {
                "chat_id": chat_id,
                "photo": photo_url,
                "caption": caption
            }
            
            response = requests.post(
                f"{self.api_url}/sendPhoto",
                json=payload
            )
            
            return response.json()
                
        except Exception as e:
            logger.error(f"Error sending Telegram photo: {str(e)}")
            return {"ok": False, "error": str(e)}

    def send_document(self, chat_id: str, document_url: str, caption: str = "") -> Dict[str, Any]:
        """Send a document via Telegram Bot API"""
        try:
            payload = {
                "chat_id": chat_id,
                "document": document_url,
                "caption": caption
            }
            
            response = requests.post(
                f"{self.api_url}/sendDocument",
                json=payload
            )
            
            return response.json()
                
        except Exception as e:
            logger.error(f"Error sending Telegram document: {str(e)}")
            return {"ok": False, "error": str(e)}

    def set_webhook(self, webhook_url: str) -> Dict[str, Any]:
        """Set webhook for receiving Telegram updates"""
        try:
            payload = {
                "url": webhook_url,
                "allowed_updates": ["message", "callback_query"]
            }
            
            response = requests.post(
                f"{self.api_url}/setWebhook",
                json=payload
            )
            
            result = response.json()
            logger.info(f"Telegram webhook set: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error setting Telegram webhook: {str(e)}")
            return {"ok": False, "error": str(e)}

    def process_webhook(self, webhook_data: Dict[str, Any], company_id: str) -> Dict[str, Any]:
        """Process incoming Telegram webhook data"""
        try:
            company = Company.objects.get(id=company_id)
            
            if "message" in webhook_data:
                self._process_incoming_message(webhook_data["message"], company)
            elif "callback_query" in webhook_data:
                self._process_callback_query(webhook_data["callback_query"], company)
            
            return {"status": "processed"}
            
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {str(e)}")
            return {"status": "failed", "error": str(e)}

    def _process_incoming_message(self, message_data: Dict[str, Any], company: Company):
        """Process a single incoming message"""
        from datetime import datetime
        
        chat_id = str(message_data["chat"]["id"])
        message_id = message_data["message_id"]
        timestamp = datetime.fromtimestamp(message_data["date"])
        
        # Get sender info
        sender_info = {
            "user_id": message_data["from"]["id"],
            "username": message_data["from"].get("username"),
            "first_name": message_data["from"].get("first_name"),
            "last_name": message_data["from"].get("last_name")
        }
        
        # Get or create conversation
        conversation, created = Conversation.objects.get_or_create(
            company=company,
            external_id=chat_id,
            platform="telegram",
            defaults={
                "participants": [sender_info],
                "status": "active"
            }
        )
        
        # Extract message content
        content = ""
        message_type = "text"
        attachments = []
        
        if "text" in message_data:
            content = message_data["text"]
        elif "photo" in message_data:
            message_type = "image"
            content = message_data.get("caption", "Photo received")
            # Get the largest photo
            photo = max(message_data["photo"], key=lambda x: x["file_size"])
            attachments.append({
                "type": "photo",
                "file_id": photo["file_id"],
                "file_size": photo["file_size"]
            })
        elif "document" in message_data:
            message_type = "document"
            content = message_data.get("caption", "Document received")
            attachments.append({
                "type": "document",
                "file_id": message_data["document"]["file_id"],
                "file_name": message_data["document"].get("file_name"),
                "mime_type": message_data["document"].get("mime_type")
            })
        elif "voice" in message_data:
            message_type = "voice"
            content = "Voice message received"
            attachments.append({
                "type": "voice",
                "file_id": message_data["voice"]["file_id"],
                "duration": message_data["voice"]["duration"]
            })
        
        # Create message
        message = Message.objects.create(
            conversation=conversation,
            direction="incoming",
            message_type=message_type,
            content=content,
            sender_info=sender_info,
            attachments=attachments,
            metadata={"telegram_message_id": message_id},
            timestamp=timestamp,
            is_processed=False
        )
        
        logger.info(f"Telegram message processed: {message_id}")

    def _process_callback_query(self, callback_data: Dict[str, Any], company: Company):
        """Process Telegram callback query (inline button press)"""
        # Handle inline keyboard button presses
        logger.info(f"Telegram callback query received: {callback_data}")
        # Implementation would depend on your bot's inline keyboard functionality

    def get_file_url(self, file_id: str) -> Optional[str]:
        """Get download URL for a file"""
        try:
            response = requests.get(f"{self.api_url}/getFile?file_id={file_id}")
            if response.status_code == 200:
                result = response.json()
                if result["ok"]:
                    file_path = result["result"]["file_path"]
                    return f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
            return None
        except Exception as e:
            logger.error(f"Error getting Telegram file URL: {str(e)}")
            return None

    def create_conversation_and_message(self, chat_id: str, message_content: str, 
                                      company: Company) -> Message:
        """Create conversation and message for testing"""
        conversation, _ = Conversation.objects.get_or_create(
            company=company,
            external_id=chat_id,
            platform="telegram",
            defaults={"participants": [{"chat_id": chat_id}]}
        )
        
        return Message.objects.create(
            conversation=conversation,
            direction="incoming",
            content=message_content,
            sender_info={"chat_id": chat_id},
            timestamp=timezone.now()
        )
