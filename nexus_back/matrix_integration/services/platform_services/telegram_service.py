import aiohttp
import json
from django.conf import settings
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class TelegramService:
    """Multi-tenant Telegram Bot API service"""
    
    def __init__(self):
        self.base_url = "https://api.telegram.org"
        
    async def send_message(self, bridge_key: str, chat_id: str, text: str, 
                          credentials: Dict) -> Dict:
        """Send message via Telegram Bot API"""
        try:
            bot_token = credentials.get('bot_token')
            if not bot_token:
                raise ValueError("Bot token not found in credentials")
                
            url = f"{self.base_url}/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    result = await response.json()
                    if response.status == 200:
                        logger.info(f"Message sent successfully via Telegram for bridge {bridge_key}")
                        return {"success": True, "message_id": result.get('result', {}).get('message_id')}
                    else:
                        logger.error(f"Failed to send Telegram message: {result}")
                        return {"success": False, "error": result.get('description')}
                        
        except Exception as e:
            logger.error(f"Error sending Telegram message for bridge {bridge_key}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def process_webhook(self, bridge_key: str, data: Dict, credentials: Dict) -> Dict:
        """Process incoming Telegram webhook"""
        try:
            # Extract message from webhook data
            if 'message' not in data:
                return {"success": False, "error": "No message in webhook data"}
            
            message = data['message']
            chat_id = str(message.get('chat', {}).get('id'))
            text = message.get('text', '')
            sender_name = message.get('from', {}).get('first_name', 'Unknown')
            
            return {
                "success": True,
                "platform": "telegram",
                "bridge_key": bridge_key,
                "sender_id": chat_id,
                "sender_name": sender_name,
                "message": text,
                "message_type": "text",
                "platform_message_id": str(message.get('message_id'))
            }
            
        except Exception as e:
            logger.error(f"Error processing Telegram webhook for bridge {bridge_key}: {str(e)}")
            return {"success": False, "error": str(e)}
