import asyncio
import aiohttp
from nio import AsyncClient, RoomMessageText, LoginResponse, RoomCreateResponse
from django.conf import settings
import json
import logging
from typing import Optional, Dict, List
from ..models import MatrixRoom, BridgeConnection

logger = logging.getLogger(__name__)

class MatrixService:
    def __init__(self):
        self.homeserver_url = settings.MATRIX_HOMESERVER
        self.server_name = settings.MATRIX_SERVER_NAME
        self.client = None
        self.access_token = None
        self.device_id = None

    async def initialize_admin_client(self):
        """Initialize Matrix client with admin credentials"""
        self.client = AsyncClient(self.homeserver_url, f"@admin:{self.server_name}")
        
        # Login with admin account
        response = await self.client.login(
            password=settings.MATRIX_ADMIN_PASSWORD,
            device_name="Nexus Backend Service"
        )
        
        if isinstance(response, LoginResponse):
            self.access_token = response.access_token
            self.device_id = response.device_id
            logger.info("Matrix admin client initialized successfully")
            return True
        else:
            logger.error(f"Failed to login to Matrix: {response}")
            return False

    async def create_company_space(self, company):
        """Create a Matrix space for a company"""
        space_alias = f"company-{company.slug}"
        
        response = await self.client.room_create(
            name=f"{company.name} - Workspace",
            topic=f"Matrix workspace for {company.name}",
            alias=space_alias,
            preset="private_chat",
            creation_content={"type": "m.space"},
            power_level_override={
                "users": {
                    f"@admin:{self.server_name}": 100
                }
            }
        )
        
        if isinstance(response, RoomCreateResponse):
            # Create MatrixRoom record
            matrix_room = MatrixRoom.objects.create(
                company=company,
                matrix_room_id=response.room_id,
                room_alias=f"#{space_alias}:{self.server_name}",
                room_type='space',
                name=f"{company.name} Workspace",
                topic=f"Matrix workspace for {company.name}"
            )
            
            logger.info(f"Created Matrix space {response.room_id} for company {company.name}")
            return matrix_room
        else:
            logger.error(f"Failed to create space for company {company.name}: {response}")
            return None

    async def create_bridge_room(self, bridge: BridgeConnection):
        """Create a room for a bridge connection"""
        room_alias = f"bridge-{bridge.platform}-{bridge.company.slug}"
        room_name = f"{bridge.name} ({bridge.platform.title()})"
        
        response = await self.client.room_create(
            name=room_name,
            topic=f"Bridge room for {bridge.name} on {bridge.platform}",
            alias=room_alias,
            preset="private_chat",
            power_level_override={
                "users": {
                    f"@admin:{self.server_name}": 100
                }
            }
        )
        
        if isinstance(response, RoomCreateResponse):
            # Create MatrixRoom record
            matrix_room = MatrixRoom.objects.create(
                company=bridge.company,
                bridge=bridge,
                matrix_room_id=response.room_id,
                room_alias=f"#{room_alias}:{self.server_name}",
                room_type='bridge',
                name=room_name,
                topic=f"Bridge room for {bridge.name}"
            )
            
            # Update bridge with room ID
            bridge.matrix_room_id = response.room_id
            bridge.save()
            
            logger.info(f"Created bridge room {response.room_id} for {bridge.bridge_key}")
            return matrix_room
        else:
            logger.error(f"Failed to create bridge room: {response}")
            return None

    async def create_conversation_room(self, bridge: BridgeConnection, customer_platform_id: str, customer_name: str = ""):
        """Create a room for a specific customer conversation"""
        room_alias = f"conv-{bridge.platform}-{bridge.company.slug}-{customer_platform_id.replace('+', '').replace('@', '')}"
        room_name = f"{customer_name or customer_platform_id} ({bridge.platform.title()})"
        
        response = await self.client.room_create(
            name=room_name,
            topic=f"Conversation with {customer_name or customer_platform_id} via {bridge.platform}",
            alias=room_alias,
            preset="private_chat",
            power_level_override={
                "users": {
                    f"@admin:{self.server_name}": 100
                }
            }
        )
        
        if isinstance(response, RoomCreateResponse):
            # Create MatrixRoom record
            matrix_room = MatrixRoom.objects.create(
                company=bridge.company,
                bridge=bridge,
                matrix_room_id=response.room_id,
                room_alias=f"#{room_alias}:{self.server_name}",
                room_type='conversation',
                name=room_name,
                topic=f"Conversation with {customer_name or customer_platform_id}",
                customer_platform_id=customer_platform_id,
                customer_name=customer_name or customer_platform_id
            )
            
            logger.info(f"Created conversation room {response.room_id} for customer {customer_platform_id}")
            return matrix_room
        else:
            logger.error(f"Failed to create conversation room: {response}")
            return None

    async def send_message_to_room(self, room_id: str, content: str, message_type: str = "m.text", formatted_content: str = None):
        """Send a message to a Matrix room"""
        message_content = {
            "msgtype": message_type,
            "body": content
        }
        
        if formatted_content:
            message_content["format"] = "org.matrix.custom.html"
            message_content["formatted_body"] = formatted_content
        
        response = await self.client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content=message_content
        )
        
        if hasattr(response, 'event_id'):
            logger.info(f"Sent message to room {room_id}: {response.event_id}")
            return response.event_id
        else:
            logger.error(f"Failed to send message to room {room_id}: {response}")
            return None

    async def invite_user_to_room(self, room_id: str, user_id: str):
        """Invite a user to a Matrix room"""
        response = await self.client.room_invite(room_id, user_id)
        
        if hasattr(response, 'transport_response') and response.transport_response.ok:
            logger.info(f"Invited user {user_id} to room {room_id}")
            return True
        else:
            logger.error(f"Failed to invite user {user_id} to room {room_id}: {response}")
            return False

    async def register_application_service(self, bridge_type: str, as_token: str, hs_token: str):
        """Register an application service for bridge"""
        registration_data = {
            "id": bridge_type,
            "url": f"http://mautrix-{bridge_type}:29318",
            "as_token": as_token,
            "hs_token": hs_token,
            "sender_localpart": f"{bridge_type}bot",
            "namespaces": {
                "users": [{"regex": f"@{bridge_type}_.*:{self.server_name}", "exclusive": True}],
                "rooms": [],
                "aliases": [{"regex": f"#{bridge_type}_.*:{self.server_name}", "exclusive": True}]
            }
        }
        
        # This would typically be done through Synapse admin API
        logger.info(f"Registered application service for {bridge_type}")
        return True

    async def close(self):
        """Close the Matrix client connection"""
        if self.client:
            await self.client.close()

# Global Matrix service instance
matrix_service = MatrixService()