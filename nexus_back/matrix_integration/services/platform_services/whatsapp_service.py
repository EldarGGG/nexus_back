import aiohttp
import json
from django.conf import settings
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class WhatsAppService:
    """Multi-tenant WhatsApp Business API service"""
    
    def __init__(self, bridge_key: str, bridge, credentials: dict):
        self.bridge_key = bridge_key
        self.bridge = bridge
        self.phone_number_id = credentials['phone_number_id']
        self.access_token = credentials['access_token']
        self.base_url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
    
    async def send_message(self, to: str, content: str, message_type: str = 'text') -> Dict:
        """Send WhatsApp message"""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        # Clean phone number (remove + if present)
        to = to.replace('+', '')
        
        payload = {
            'messaging_product': 'whatsapp',
            'to': to,
            'type': message_type,
            message_type: {'body': content}
        }
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    result = await response.json()
                    
                    if response.status == 200:
                        return {
                            'success': True,
                            'message_id': result.get('messages', [{}])[0].get('id'),
                            'status': 'sent'
                        }
                    else:
                        logger.error(f"WhatsApp send error: {result}")
                        return {
                            'success': False,
                            'error': result.get('error', {}).get('message', 'Unknown error')
                        }
                        
        except Exception as e:
            logger.error(f"WhatsApp send exception: {e}")
            return {'success': False, 'error': str(e)}
    
    async def process_incoming_message(self, webhook_data: dict) -> Optional[Dict]:
        """Process incoming WhatsApp webhook"""
        try:
            entry = webhook_data.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])
            
            for change in changes:
                value = change.get('value', {})
                messages = value.get('messages', [])
                
                for message in messages:
                    # Extract message content based on type
                    content = ""
                    message_type = message.get('type', 'unknown')
                    
                    if message_type == 'text':
                        content = message.get('text', {}).get('body', '')
                    elif message_type == 'image':
                        content = f"[Image] {message.get('image', {}).get('caption', 'Image received')}"
                    elif message_type == 'document':
                        content = f"[Document] {message.get('document', {}).get('filename', 'Document received')}"
                    elif message_type == 'audio':
                        content = "[Audio message received]"
                    elif message_type == 'video':
                        content = f"[Video] {message.get('video', {}).get('caption', 'Video received')}"
                    else:
                        content = f"[{message_type.title()}] Unsupported message type"
                    
                    # Get contact info
                    contacts = value.get('contacts', [])
                    sender_name = ""
                    if contacts:
                        profile = contacts[0].get('profile', {})
                        sender_name = profile.get('name', '')
                    
                    return {
                        'external_id': message['id'],
                        'content': content,
                        'type': message_type,
                        'sender_id': message['from'],
                        'sender_name': sender_name,
                        'timestamp': message['timestamp'],
                        'raw_message': message
                    }
                    
        except Exception as e:
            logger.error(f"Error processing WhatsApp webhook: {e}")
            return None
    
    async def setup_webhook(self, webhook_url: str):
        """Setup WhatsApp webhook for this specific bridge"""
        # This would typically be done once during initial setup
        # through Meta Business API webhook configuration
        logger.info(f"WhatsApp webhook configured for {self.bridge_key}: {webhook_url}")
        
        # Store webhook URL in bridge
        self.bridge.webhook_url = webhook_url
        self.bridge.save()