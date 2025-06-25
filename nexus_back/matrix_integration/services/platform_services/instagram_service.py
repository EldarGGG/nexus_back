import aiohttp
import json
from django.conf import settings
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class InstagramService:
    """Multi-tenant Instagram Messaging API service"""
    
    def __init__(self):
        self.base_url = "https://graph.facebook.com/v18.0"
        
    async def send_message(self, bridge_key: str, recipient_id: str, text: str, 
                          credentials: Dict) -> Dict:
        """Send message via Instagram Messaging API"""
        try:
            access_token = credentials.get('access_token')
            if not access_token:
                raise ValueError("Access token not found in credentials")
                
            # Instagram uses Facebook Graph API for messaging
            url = f"{self.base_url}/me/messages"
            payload = {
                "recipient": {"id": recipient_id},
                "message": {"text": text},
                "access_token": access_token
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    result = await response.json()
                    if response.status == 200:
                        logger.info(f"Message sent successfully via Instagram for bridge {bridge_key}")
                        return {"success": True, "message_id": result.get('message_id')}
                    else:
                        logger.error(f"Failed to send Instagram message: {result}")
                        return {"success": False, "error": result.get('error', {}).get('message')}
                        
        except Exception as e:
            logger.error(f"Error sending Instagram message for bridge {bridge_key}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def process_webhook(self, bridge_key: str, data: Dict, credentials: Dict) -> Dict:
        """Process incoming Instagram webhook"""
        try:
            # Extract message from webhook data
            if 'entry' not in data:
                return {"success": False, "error": "No entry in webhook data"}
            
            for entry in data['entry']:
                if 'messaging' in entry:
                    for messaging_event in entry['messaging']:
                        if 'message' in messaging_event:
                            message = messaging_event['message']
                            sender_id = messaging_event['sender']['id']
                            text = message.get('text', '')
                            
                            return {
                                "success": True,
                                "platform": "instagram",
                                "bridge_key": bridge_key,
                                "sender_id": sender_id,
                                "sender_name": "Instagram User",
                                "message": text,
                                "message_type": "text",
                                "platform_message_id": message.get('mid')
                            }
            
            return {"success": False, "error": "No processable message found"}
            
        except Exception as e:
            logger.error(f"Error processing Instagram webhook for bridge {bridge_key}: {str(e)}")
            return {"success": False, "error": str(e)}
