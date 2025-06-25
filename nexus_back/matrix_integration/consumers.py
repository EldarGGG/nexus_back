import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


class MatrixConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for Matrix room events"""
    
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'matrix_room_{self.room_name}'
        
        # Check authentication
        if self.scope["user"] == AnonymousUser():
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connected to Matrix room: {self.room_name}")

    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        logger.info(f"WebSocket disconnected from Matrix room: {self.room_name}")

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'send_message':
                await self.send_matrix_message(text_data_json)
            elif message_type == 'typing_start':
                await self.handle_typing_start()
            elif message_type == 'typing_stop':
                await self.handle_typing_stop()
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON'
            }))
        except Exception as e:
            logger.error(f"Error in MatrixConsumer receive: {str(e)}")
            await self.send(text_data=json.dumps({
                'error': 'Internal error'
            }))

    async def send_matrix_message(self, data):
        """Send message to Matrix room"""
        message = data.get('message', '')
        if not message:
            return
        
        # TODO: Integrate with Matrix client to send message
        # For now, broadcast to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'matrix_message',
                'message': message,
                'sender': self.scope["user"].email,
                'timestamp': asyncio.get_event_loop().time()
            }
        )

    async def handle_typing_start(self):
        """Handle typing indicator start"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user': self.scope["user"].email,
                'typing': True
            }
        )

    async def handle_typing_stop(self):
        """Handle typing indicator stop"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user': self.scope["user"].email,
                'typing': False
            }
        )

    # Receive message from room group
    async def matrix_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'matrix_message',
            'message': event['message'],
            'sender': event['sender'],
            'timestamp': event['timestamp']
        }))

    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing_indicator',
            'user': event['user'],
            'typing': event['typing']
        }))


class CompanyConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for company-wide events"""
    
    async def connect(self):
        self.company_id = self.scope['url_route']['kwargs']['company_id']
        self.company_group_name = f'company_{self.company_id}'
        
        # Check authentication and company membership
        if self.scope["user"] == AnonymousUser():
            await self.close()
            return
        
        # TODO: Verify user belongs to company
        
        # Join company group
        await self.channel_layer.group_add(
            self.company_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connected to company: {self.company_id}")

    async def disconnect(self, close_code):
        # Leave company group
        if hasattr(self, 'company_group_name'):
            await self.channel_layer.group_discard(
                self.company_group_name,
                self.channel_name
            )
        logger.info(f"WebSocket disconnected from company: {self.company_id}")

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            # Handle different message types
            if message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON'
            }))

    # Receive various company events
    async def bridge_status_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'bridge_status_update',
            'bridge_id': event['bridge_id'],
            'status': event['status'],
            'timestamp': event['timestamp']
        }))

    async def new_message_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_message_notification',
            'bridge_id': event['bridge_id'],
            'customer_id': event['customer_id'],
            'message_preview': event['message_preview'],
            'timestamp': event['timestamp']
        }))

    async def ai_response_generated(self, event):
        await self.send(text_data=json.dumps({
            'type': 'ai_response_generated',
            'message_id': event['message_id'],
            'response': event['response'],
            'confidence': event['confidence'],
            'timestamp': event['timestamp']
        }))


class BridgeConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for bridge-specific events"""
    
    async def connect(self):
        self.bridge_id = self.scope['url_route']['kwargs']['bridge_id']
        self.bridge_group_name = f'bridge_{self.bridge_id}'
        
        # Check authentication
        if self.scope["user"] == AnonymousUser():
            await self.close()
            return
        
        # TODO: Verify user has access to this bridge
        
        # Join bridge group
        await self.channel_layer.group_add(
            self.bridge_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connected to bridge: {self.bridge_id}")

    async def disconnect(self, close_code):
        # Leave bridge group
        if hasattr(self, 'bridge_group_name'):
            await self.channel_layer.group_discard(
                self.bridge_group_name,
                self.channel_name
            )
        logger.info(f"WebSocket disconnected from bridge: {self.bridge_id}")

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'send_message':
                await self.send_bridge_message(text_data_json)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON'
            }))

    async def send_bridge_message(self, data):
        """Send message through bridge"""
        # TODO: Integrate with bridge manager to send message
        pass

    # Receive bridge events
    async def message_received(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_received',
            'message_id': event['message_id'],
            'content': event['content'],
            'sender': event['sender'],
            'timestamp': event['timestamp']
        }))

    async def message_sent(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_sent',
            'message_id': event['message_id'],
            'content': event['content'],
            'recipient': event['recipient'],
            'timestamp': event['timestamp']
        }))

    async def connection_status_change(self, event):
        await self.send(text_data=json.dumps({
            'type': 'connection_status_change',
            'status': event['status'],
            'message': event.get('message', ''),
            'timestamp': event['timestamp']
        }))
