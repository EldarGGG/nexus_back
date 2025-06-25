import asyncio
import json
from typing import Dict, List, Optional
from django.conf import settings
from django.utils import timezone
from ..models import BridgeConnection, BridgeCredentials, BridgeMessage, MatrixRoom, AIAssistantConfig
from .matrix_service import matrix_service
from .ai_service import AIService
from .platform_services.whatsapp_service import WhatsAppService
from .platform_services.telegram_service import TelegramService
from .platform_services.instagram_service import InstagramService
import logging

logger = logging.getLogger(__name__)

class BridgeManager:
    def __init__(self):
        self.platform_services = {}
    
    async def initialize_bridge(self, bridge_connection: BridgeConnection) -> bool:
        """Initialize bridge connection to external platform"""
        try:
            platform = bridge_connection.platform
            if platform not in ['whatsapp', 'telegram', 'instagram']:
                logger.error(f"Unsupported platform: {platform}")
                return False
            
            credentials = BridgeCredentials.objects.filter(bridge=bridge_connection).first()
            
            if not credentials:
                logger.error(f"No credentials found for bridge {bridge_connection.id}")
                return False
                
            # Create appropriate service instance with credentials
            credentials_dict = json.loads(credentials.credentials_json)
            
            # Create service instance for this specific bridge
            bridge_key = f"{platform}_{bridge_connection.id}"
            
            if platform == 'whatsapp':
                platform_service = WhatsAppService(bridge_key, bridge_connection, credentials_dict)
            elif platform == 'telegram':
                platform_service = TelegramService(bridge_key, bridge_connection, credentials_dict)
            elif platform == 'instagram':
                platform_service = InstagramService(bridge_key, bridge_connection, credentials_dict)
                
            # Save in platform_services dictionary for reuse
            self.platform_services[bridge_key] = platform_service
                
            # Initialize platform-specific connection
            success = await platform_service.initialize_connection(
                bridge_connection.company.id,
                credentials_dict
            )
            
            if success:
                bridge_connection.status = 'connected'
                bridge_connection.last_connected = timezone.now()
                bridge_connection.save()
                
                # Initialize Matrix bridge room if needed
                await matrix_service.initialize_company_bridge(bridge_connection.company)
                
                logger.info(f"Bridge {bridge_connection.id} initialized successfully")
                return True
            else:
                bridge_connection.status = 'error'
                bridge_connection.save()
                logger.error(f"Failed to initialize bridge {bridge_connection.id}")
                return False
                
        except Exception as e:
            logger.exception(f"Error initializing bridge: {e}")
            bridge_connection.status = 'error'
            bridge_connection.save()
            return False
    
    async def send_message(self, bridge_connection: BridgeConnection, 
                         external_id: str, message: str) -> bool:
        """Send message to external platform via bridge"""
        try:
            platform = bridge_connection.platform
            bridge_key = f"{platform}_{bridge_connection.id}"
            
            # Check if we already have a service instance for this bridge
            if bridge_key not in self.platform_services:
                # Try to initialize it
                success = await self.initialize_bridge(bridge_connection)
                if not success:
                    logger.error(f"Failed to initialize platform service for {platform}")
                    return False
            
            platform_service = self.platform_services[bridge_key]
            
            # Send message via platform service
            success = await platform_service.send_message(
                bridge_connection.company.id, 
                external_id, 
                message
            )
            
            if success:
                # Create message record
                BridgeMessage.objects.create(
                    bridge=bridge_connection,
                    external_id=external_id,
                    content=message,
                    direction='outbound',
                    status='sent'
                )
                return True
            else:
                logger.error(f"Failed to send message via bridge {bridge_connection.id}")
                return False
                
        except Exception as e:
            logger.exception(f"Error sending message: {e}")
            return False
    
    async def process_webhook_data(self, platform: str, company_id: str, webhook_data: dict) -> bool:
        """Process incoming webhook data from external platform"""
        try:
            if platform not in ['whatsapp', 'telegram', 'instagram']:
                logger.error(f"Unsupported platform: {platform}")
                return False
                
            # Find appropriate bridge connection
            bridge_connection = BridgeConnection.objects.filter(
                company__id=company_id,
                platform=platform,
                status='connected'
            ).first()
            
            if not bridge_connection:
                logger.error(f"No active bridge found for company {company_id}, platform {platform}")
                return False
                
            bridge_key = f"{platform}_{bridge_connection.id}"
            
            # Get or create service for this bridge
            if bridge_key not in self.platform_services:
                # Try to initialize it
                success = await self.initialize_bridge(bridge_connection)
                if not success:
                    logger.error(f"Failed to initialize platform service for {platform}")
                    return False
            
            platform_service = self.platform_services[bridge_key]
            
            # Parse webhook data using platform-specific logic
            parsed_data = platform_service.parse_webhook_data(webhook_data)
            if not parsed_data:
                logger.error(f"Failed to parse webhook data for platform {platform}")
                return False
            
            # Find bridge connection
            bridge_connection = BridgeConnection.objects.filter(
                company__id=company_id,
                platform=platform,
                status='connected'
            ).first()
            
            if not bridge_connection:
                logger.error(f"No active bridge found for company {company_id}, platform {platform}")
                return False
            
            # Create message record
            message = BridgeMessage.objects.create(
                bridge=bridge_connection,
                external_id=parsed_data['sender_id'],
                customer_name=parsed_data.get('sender_name', ''),
                content=parsed_data['message'],
                direction='inbound',
                status='received',
                raw_data=json.dumps(webhook_data)
            )
            
            # Forward to Matrix
            success = await self._forward_to_matrix(bridge_connection, message)
            
            return success
            
        except Exception as e:
            logger.exception(f"Error processing webhook: {e}")
            return False
    
    async def _forward_to_matrix(self, bridge_connection: BridgeConnection, 
                               message: BridgeMessage) -> bool:
        """Forward message to Matrix room"""
        try:
            # Get company room
            room = await matrix_service.get_company_bridge_room(bridge_connection.company.id)
            if not room:
                logger.error(f"No Matrix room found for company {bridge_connection.company.id}")
                return False
            
            # Format message for Matrix
            sender_prefix = f"{message.customer_name} ({message.external_id})" if message.customer_name else message.external_id
            formatted_message = f"[{bridge_connection.platform.upper()}] {sender_prefix}: {message.content}"
            
            # Send via Matrix service
            await matrix_service.send_message_via_bridge(
                bridge_connection.platform,
                message.external_id,
                bridge_connection.company.id,
                formatted_message
            )
            
            # Process with AI if enabled
            await self._process_with_ai(bridge_connection, message)
            
            return True
            
        except Exception as e:
            logger.exception(f"Error forwarding to Matrix: {e}")
            return False
    
    async def _process_with_ai(self, bridge_connection: BridgeConnection, 
                             message: BridgeMessage) -> None:
        """Process message with AI if configured"""
        try:
            # Check if AI is enabled for this company
            config = AIAssistantConfig.objects.filter(company=bridge_connection.company).first()
            if not config or not config.enabled:
                logger.debug(f"AI not enabled for company {bridge_connection.company.id}")
                return
            
            # Get recent conversation context
            recent_messages = BridgeMessage.objects.filter(
                bridge=bridge_connection,
                external_id=message.external_id
            ).order_by('-created_at')[:10]
            
            context = {
                'company': bridge_connection.company.name,
                'customer_name': message.customer_name,
                'platform': bridge_connection.platform,
                'recent_messages': [
                    {
                        'content': msg.content,
                        'direction': msg.direction,
                        'timestamp': msg.created_at.isoformat()
                    } for msg in reversed(list(recent_messages))
                ]
            }
            
            # Get AI service from ai_service.py
            ai_instance = AIService()
            
            # Generate response async
            response = ai_instance.generate_response_sync(message.content, context, config)
            
            if response and response.get('content'):
                # Send response back
                await self.send_message(
                    bridge_connection,
                    message.external_id,
                    response['content']
                )
                
                logger.info(f"AI response sent for message {message.id} with confidence {response.get('confidence', 0)}")
            
        except Exception as e:
            logger.exception(f"Error processing with AI: {e}")

# Initialize bridge manager
bridge_manager = BridgeManager()
