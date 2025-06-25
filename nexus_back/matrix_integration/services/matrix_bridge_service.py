"""
Matrix Client Service for Bridge Integration
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from nio import AsyncClient, MatrixRoom, RoomMessageText, Event
from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async
from messaging.models import Conversation, Message
from companies.models import Company

logger = logging.getLogger(__name__)


class MatrixBridgeService:
    """Service for Matrix bridge integration"""
    
    def __init__(self):
        self.homeserver = getattr(settings, 'MATRIX_HOMESERVER', 'http://localhost:8008')
        self.user_id = getattr(settings, 'MATRIX_USER_ID', '@nexus_bot:matrix.nexus.local')
        self.access_token = getattr(settings, 'MATRIX_ACCESS_TOKEN', '')
        self.client = None
        self._bridge_room_mapping = {}

    async def initialize(self):
        """Initialize Matrix client"""
        self.client = AsyncClient(self.homeserver, self.user_id)
        if self.access_token:
            self.client.access_token = self.access_token
        else:
            # Login if no access token
            response = await self.client.login(
                password=getattr(settings, 'MATRIX_ADMIN_PASSWORD', 'admin123')
            )
            if response:
                self.access_token = self.client.access_token
                logger.info("Matrix client logged in successfully")
        
        # Set up event listeners
        self.client.add_event_callback(self.on_message, RoomMessageText)
        
    async def start_sync(self):
        """Start Matrix client sync"""
        if not self.client:
            await self.initialize()
        
        try:
            await self.client.sync_forever(timeout=30000)
        except Exception as e:
            logger.error(f"Matrix sync error: {e}")
            await asyncio.sleep(5)
            await self.start_sync()

    async def on_message(self, room: MatrixRoom, event: RoomMessageText):
        """Handle incoming Matrix messages from bridges"""
        try:
            # Skip our own messages
            if event.sender == self.user_id:
                return
                
            # Get bridge info from room topic or state
            bridge_info = await self.get_bridge_info(room.room_id)
            if not bridge_info:
                return
                
            platform = bridge_info.get('platform')
            external_id = bridge_info.get('external_id')
            company_id = bridge_info.get('company_id')
            
            if not all([platform, external_id, company_id]):
                logger.warning(f"Missing bridge info for room {room.room_id}")
                return
                
            # Process the message
            await self.process_bridge_message(
                platform=platform,
                external_id=external_id, 
                company_id=company_id,
                content=event.body,
                sender=event.sender,
                timestamp=event.server_timestamp
            )
            
        except Exception as e:
            logger.error(f"Error processing Matrix message: {e}")

    async def process_bridge_message(self, platform: str, external_id: str, 
                                   company_id: str, content: str, sender: str, 
                                   timestamp: int):
        """Process incoming message from bridge"""
        try:
            # Get company
            company = await sync_to_async(Company.objects.get)(id=company_id)
            
            # Get or create conversation
            conversation, created = await sync_to_async(
                Conversation.objects.get_or_create
            )(
                company=company,
                external_id=external_id,
                platform=platform,
                defaults={
                    "participants": [{"id": external_id, "platform": platform}],
                    "status": "active"
                }
            )
            
            # Create message
            message = await sync_to_async(Message.objects.create)(
                conversation=conversation,
                direction="incoming",
                message_type="text",
                content=content,
                sender_info={"matrix_sender": sender, "platform": platform},
                timestamp=timezone.datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc),
                is_processed=True
            )
            
            logger.info(f"Matrix bridge message processed: {platform} - {external_id}")
            
            # Trigger AI response if enabled
            company_settings = await sync_to_async(
                lambda: getattr(company, 'settings', None)
            )()
            
            if company_settings and company_settings.ai_enabled and company_settings.auto_response_enabled:
                from ..tasks import generate_ai_response
                generate_ai_response.delay(message.id)
                
        except Exception as e:
            logger.error(f"Error processing bridge message: {e}")

    async def send_message_via_bridge(self, platform: str, external_id: str, 
                                    company_id: str, content: str, 
                                    message_type: str = 'text') -> Dict[str, Any]:
        """Send message through Matrix bridge"""
        try:
            logger.debug(f"send_message_via_bridge called with platform={platform}, external_id={external_id}, company_id={company_id} (type: {type(company_id)}), content={content}")
            
            if not self.client:
                await self.initialize()
                
            # Get or create bridge room
            room_id = await self.get_or_create_bridge_room(
                platform=platform,
                external_id=external_id, 
                company_id=str(company_id)  # Ensure string conversion
            )
            
            logger.debug(f"Bridge room_id: {room_id}")
            
            if not room_id:
                return {"status": "failed", "error": "Could not create bridge room"}
                
            # Send message to room
            logger.debug(f"Sending message to room {room_id}: {content}")
            response = await self.client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": content
                }
            )
            
            logger.debug(f"Matrix response: {response}")
            
            if hasattr(response, 'event_id'):
                return {
                    "status": "success", 
                    "message_id": response.event_id,
                    "room_id": room_id
                }
            else:
                return {"status": "failed", "error": str(response)}
                
        except Exception as e:
            logger.error(f"Error sending message via bridge: {e}")
            return {"status": "failed", "error": str(e)}

    async def get_or_create_bridge_room(self, platform: str, external_id: str, 
                                      company_id: str) -> Optional[str]:
        """Get or create Matrix room for bridge conversation"""
        try:
            # Ensure company_id is a string
            company_id = str(company_id)
            
            # Check if room already exists
            room_alias = f"#{platform}_{external_id}_{company_id}:matrix.nexus.local"
            
            # Try to resolve room alias
            try:
                response = await self.client.room_resolve_alias(room_alias)
                if hasattr(response, 'room_id') and response.room_id:
                    return response.room_id
            except Exception as e:
                logger.debug(f"Room alias {room_alias} not found, will create new room: {e}")
                
            # Create new room
            response = await self.client.room_create(
                alias=f"{platform}_{external_id}_{company_id}",
                name=f"{platform.title()} - {external_id}",
                topic=f"Bridge room for {platform} user {external_id} (Company: {company_id})",
                invite=[],  # Add bridge bot users here
                is_direct=True
            )
            
            if hasattr(response, 'room_id'):
                # Store bridge info in room state
                await self.client.room_put_state(
                    room_id=response.room_id,
                    event_type="m.bridge.info",
                    content={
                        "platform": platform,
                        "external_id": external_id,
                        "company_id": str(company_id)  # Ensure string conversion
                    }
                )
                return response.room_id
                
        except Exception as e:
            logger.error(f"Error creating bridge room: {e}")
            
        return None

    async def get_bridge_info(self, room_id: str) -> Optional[Dict[str, str]]:
        """Get bridge information from room state"""
        try:
            response = await self.client.room_get_state_event(
                room_id=room_id,
                event_type="m.bridge.info"
            )
            
            if hasattr(response, 'content'):
                return response.content
                
        except Exception as e:
            logger.debug(f"No bridge info found for room {room_id}: {e}")
            
        return None

    async def list_conversations(self, company_id: str) -> List[Dict[str, Any]]:
        """List all bridge conversations for a company"""
        try:
            if not self.client:
                await self.initialize()
                
            rooms = await self.client.joined_rooms()
            conversations = []
            
            for room_id in rooms.rooms:
                bridge_info = await self.get_bridge_info(room_id)
                if bridge_info and bridge_info.get('company_id') == company_id:
                    room = await self.client.room_get_info(room_id)
                    conversations.append({
                        "room_id": room_id,
                        "platform": bridge_info.get('platform'),
                        "external_id": bridge_info.get('external_id'),
                        "name": getattr(room, 'display_name', f"{bridge_info.get('platform')} - {bridge_info.get('external_id')}"),
                        "topic": getattr(room, 'topic', ''),
                        "member_count": getattr(room, 'member_count', 0)
                    })
                    
            return conversations
            
        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            return []

    async def close(self):
        """Close Matrix client connection"""
        if self.client:
            await self.client.close()

    async def initialize_company_bridge(self, company_id: str, platform: str, config_data: dict):
        """Initialize Matrix bridge for a specific company and platform"""
        try:
            # Ensure client is initialized
            if not self.client:
                await self.initialize()
            
            # Create bridge room for the company/platform combination
            room_id = await self.get_or_create_bridge_room(
                platform=platform,
                external_id=f"company_{company_id}",
                company_id=company_id
            )
            
            if room_id:
                # Store company bridge configuration in room state
                await self.client.room_put_state(
                    room_id=room_id,
                    event_type="m.bridge.company.config",
                    content={
                        "company_id": company_id,
                        "platform": platform,
                        "initialized_at": timezone.now().isoformat(),
                        "bridge_version": "1.0",
                        "capabilities": ["send", "receive", "typing", "read_receipts"]
                    }
                )
                
                logger.info(f"Company bridge initialized: {company_id} - {platform} - Room: {room_id}")
                return {"status": "success", "room_id": room_id}
            else:
                raise Exception("Failed to create bridge room")
                
        except Exception as e:
            logger.error(f"Error initializing company bridge for {company_id}/{platform}: {e}")
            return {"status": "error", "error": str(e)}

    async def get_company_bridge_room(self, company_id: str, platform: str) -> Optional[str]:
        """Get existing bridge room for company/platform"""
        try:
            room_alias = f"#{platform}_company_{company_id}:matrix.nexus.local"
            response = await self.client.room_resolve_alias(room_alias)
            
            if hasattr(response, 'room_id') and response.room_id:
                return response.room_id
                
        except Exception as e:
            logger.debug(f"Bridge room not found for {company_id}/{platform}: {e}")
            
        return None

    async def send_company_message(self, company_id: str, platform: str, external_id: str, 
                                 content: str, message_type: str = "text") -> dict:
        """Send message through company-specific bridge"""
        try:
            # Get or create bridge room for this specific conversation
            room_id = await self.get_or_create_bridge_room(
                platform=platform,
                external_id=external_id,
                company_id=company_id
            )
            
            if not room_id:
                return {"status": "error", "error": "Failed to get bridge room"}
            
            # Format message based on type
            message_content = {
                "msgtype": f"m.{message_type}",
                "body": content
            }
            
            if message_type == "image":
                message_content["url"] = content  # Assume content is image URL for images
            elif message_type == "file":
                message_content["filename"] = content.split('/')[-1]
                message_content["url"] = content
            
            # Send message to bridge room
            response = await self.client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content=message_content
            )
            
            if hasattr(response, 'event_id'):
                logger.debug(f"Company message sent: {company_id}/{platform} - Event: {response.event_id}")
                return {
                    "status": "success",
                    "message_id": response.event_id,
                    "room_id": room_id
                }
            else:
                return {"status": "error", "error": "Failed to send message"}
                
        except Exception as e:
            logger.error(f"Error sending company message: {e}")
            return {"status": "error", "error": str(e)}

# Global Matrix service instance
matrix_service = MatrixBridgeService()
