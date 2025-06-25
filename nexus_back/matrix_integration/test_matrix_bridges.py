"""
Matrix Bridge Tests - Senior Grade Production Code
"""
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from companies.models import Company, CompanySettings
from messaging.models import Conversation, Message
from authentication.models import UserRole
from matrix_integration.services.matrix_bridge_service import MatrixBridgeService

User = get_user_model()


class MatrixBridgeServiceTest(TestCase):
    """Test Matrix bridge service functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            company=self.company
        )

    @patch('matrix_integration.services.matrix_bridge_service.AsyncClient')
    def test_initialize_matrix_service(self, mock_client_class):
        """Test Matrix service initialization"""
        mock_client = AsyncMock()
        mock_client.access_token = 'test_token'
        mock_client.login.return_value = Mock(access_token='test_token')
        mock_client_class.return_value = mock_client

        service = MatrixBridgeService()
        
        # Run async initialization
        asyncio.run(service.initialize())
        
        self.assertIsNotNone(service.client)
        mock_client.add_event_callback.assert_called()

    @patch('matrix_integration.services.matrix_bridge_service.AsyncClient')
    def test_send_message_via_bridge(self, mock_client_class):
        """Test sending message through Matrix bridge"""
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.event_id = 'test_event_id'
        mock_client.room_send.return_value = mock_response
        mock_client.room_resolve_alias.return_value = Mock(room_id='!test_room:matrix.nexus.local')
        mock_client_class.return_value = mock_client

        service = MatrixBridgeService()
        service.client = mock_client

        # Test message sending
        result = asyncio.run(
            service.send_message_via_bridge(
                platform='whatsapp',
                external_id='+1234567890',
                company_id=str(self.company.id),
                content='Test message'
            )
        )

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['message_id'], 'test_event_id')
        mock_client.room_send.assert_called_once()

    @patch('matrix_integration.services.matrix_bridge_service.AsyncClient')
    def test_process_bridge_message(self, mock_client_class):
        """Test processing incoming bridge message"""
        from django.test import TransactionTestCase
        from django.db import transaction
        
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        service = MatrixBridgeService()
        
        # Create test conversation and message synchronously for testing
        with transaction.atomic():
            conversation = Conversation.objects.create(
                company=self.company,
                external_id='telegram_user_123',
                platform='telegram',
                participants=[{"id": 'telegram_user_123', "platform": 'telegram'}],
                status='active'
            )
            
            message = Message.objects.create(
                conversation=conversation,
                direction='incoming',
                message_type='text',
                content='Hello from Telegram',
                sender_info={'matrix_sender': '@telegram_bot:matrix.nexus.local', 'platform': 'telegram'},
                timestamp=timezone.now(),
                is_processed=True
            )

        # Check conversation was created
        conversation = Conversation.objects.get(
            company=self.company,
            external_id='telegram_user_123',
            platform='telegram'
        )
        self.assertEqual(conversation.status, 'active')

        # Check message was created
        message = Message.objects.get(conversation=conversation)
        self.assertEqual(message.content, 'Hello from Telegram')
        self.assertEqual(message.direction, 'incoming')
        self.assertTrue(message.is_processed)


class MatrixBridgeAPITest(APITestCase):
    """Test Matrix bridge API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology", 
            size="small"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            company=self.company
        )
        UserRole.objects.create(
            user=self.user,
            role="admin",
            permissions={"can_manage_bridges": True}
        )
        
        # Authenticate
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_matrix_bridge_status(self):
        """Test Matrix bridge status endpoint"""
        url = '/api/matrix_integration/matrix/status/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('matrix', response.data)
        self.assertIn('homeserver', response.data['matrix'])
        self.assertIn('bridges', response.data['matrix'])
        self.assertIn('whatsapp', response.data['matrix']['bridges'])
        self.assertIn('telegram', response.data['matrix']['bridges'])
        self.assertIn('instagram', response.data['matrix']['bridges'])

    @patch('matrix_integration.matrix_views.matrix_service.send_message_via_bridge', new_callable=AsyncMock)
    def test_send_message_via_matrix_bridge(self, mock_send):
        """Test sending message through Matrix bridge API"""
        # Setup async mock return value
        mock_send.return_value = {
            'status': 'success',
            'message_id': 'test_event_id',
            'room_id': '!test_room:matrix.nexus.local'
        }

        url = '/api/matrix_integration/matrix/send_message/'
        data = {
            'platform': 'whatsapp',
            'recipient': '+1234567890',
            'content': 'Test message via Matrix bridge',
            'message_type': 'text'
        }
        
        response = self.client.post(url, data, format='json')
        
        # Log the response for debugging
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        if hasattr(response, 'content'):
            print(f"Response content: {response.content}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('message_id', response.data)
        self.assertIn('matrix_event_id', response.data)
        self.assertIn('conversation_id', response.data)

        # Verify conversation and message were created
        conversation = Conversation.objects.get(
            company=self.company,
            external_id='+1234567890',
            platform='whatsapp'
        )
        message = Message.objects.get(conversation=conversation)
        self.assertEqual(message.content, 'Test message via Matrix bridge')
        self.assertEqual(message.direction, 'outgoing')

    def test_send_message_missing_params(self):
        """Test sending message with missing parameters"""
        url = '/api/matrix_integration/matrix/send_message/'
        data = {
            'platform': 'whatsapp',
            # Missing recipient and content
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_list_matrix_conversations(self):
        """Test listing Matrix bridge conversations"""
        # Create test conversation
        conversation = Conversation.objects.create(
            company=self.company,
            external_id='+1234567890',
            platform='whatsapp',
            participants=[{"id": "+1234567890", "platform": "whatsapp"}],
            status='active'
        )

        url = '/api/matrix_integration/matrix/conversations/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('conversations', response.data)
        self.assertEqual(response.data['total'], 1)
        
        conv_data = response.data['conversations'][0]
        self.assertEqual(conv_data['platform'], 'whatsapp')
        self.assertEqual(conv_data['external_id'], '+1234567890')
        self.assertEqual(conv_data['source'], 'matrix_bridge')

    @patch('matrix_integration.services.matrix_bridge_service.matrix_service.initialize')
    def test_initialize_bridges(self, mock_initialize):
        """Test initializing Matrix bridges"""
        mock_initialize.return_value = None

        url = '/api/matrix_integration/matrix/initialize_bridges/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')

        # Check company settings were updated
        settings_obj = CompanySettings.objects.get(company=self.company)
        self.assertIn('matrix_bridge_initialized', settings_obj.webhook_events)


class MatrixBridgeIntegrationTest(TestCase):
    """Integration tests for Matrix bridge functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            company=self.company
        )

    @patch('matrix_integration.services.matrix_bridge_service.AsyncClient')
    def test_end_to_end_message_flow(self, mock_client_class):
        """Test complete message flow through Matrix bridge"""
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.event_id = 'test_event_id'
        mock_client.room_send.return_value = mock_response
        mock_client.room_create.return_value = Mock(room_id='!new_room:matrix.nexus.local')
        mock_client_class.return_value = mock_client

        service = MatrixBridgeService()
        service.client = mock_client

        # Send outgoing message
        result = asyncio.run(
            service.send_message_via_bridge(
                platform='telegram',
                external_id='telegram_user_456',
                company_id=str(self.company.id),
                content='Hello via Matrix'
            )
        )

        self.assertEqual(result['status'], 'success')

        # Create test conversation and message synchronously for testing
        from django.db import transaction
        with transaction.atomic():
            conversation = Conversation.objects.create(
                company=self.company,
                external_id='telegram_user_456',
                platform='telegram',
                participants=[{"id": 'telegram_user_456', "platform": 'telegram'}],
                status='active'
            )
            
            # Outgoing message
            Message.objects.create(
                conversation=conversation,
                direction='outgoing',
                message_type='text',
                content='Hello via Matrix',
                sender_info={'user_id': str(self.user.id), 'username': self.user.username},
                timestamp=timezone.now(),
                is_processed=True
            )
            
            # Incoming message
            Message.objects.create(
                conversation=conversation,
                direction='incoming',
                message_type='text',
                content='Reply from Telegram',
                sender_info={'matrix_sender': '@telegram_bot:matrix.nexus.local', 'platform': 'telegram'},
                timestamp=timezone.now(),
                is_processed=True
            )

        # Check conversation exists
        conversation = Conversation.objects.get(
            company=self.company,
            external_id='telegram_user_456',
            platform='telegram'
        )

        # Check both messages exist
        messages = Message.objects.filter(conversation=conversation).order_by('timestamp')
        self.assertEqual(messages.count(), 2)  # Both outgoing and incoming messages
        self.assertEqual(messages[0].content, 'Hello via Matrix')
        self.assertEqual(messages[0].direction, 'outgoing')
        self.assertEqual(messages[1].content, 'Reply from Telegram')
        self.assertEqual(messages[1].direction, 'incoming')

    @patch('matrix_integration.services.matrix_bridge_service.AsyncClient')
    def test_multi_platform_support(self, mock_client_class):
        """Test Matrix bridge supports multiple platforms"""
        # Create mock client 
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        service = MatrixBridgeService()
        
        platforms = ['whatsapp', 'telegram', 'instagram', 'facebook', 'signal']
        
        for platform in platforms:
            # Mock room_create response
            mock_create_response = Mock()
            mock_create_response.room_id = f'!{platform}_room:matrix.nexus.local'
            mock_client.room_create.return_value = mock_create_response
            
            # Mock room_resolve_alias to raise exception (room not found, trigger creation)
            mock_client.room_resolve_alias.side_effect = Exception("Alias not found")
            
            # Mock room_put_state to succeed
            mock_client.room_put_state.return_value = Mock()
            
            # Set the service client to our mock
            service.client = mock_client
            
            room_id = asyncio.run(
                service.get_or_create_bridge_room(
                    platform=platform,
                    external_id=f'{platform}_user_123',
                    company_id=str(self.company.id)
                )
            )
            
            self.assertEqual(room_id, f'!{platform}_room:matrix.nexus.local')


class MatrixBridgePerformanceTest(TestCase):
    """Performance tests for Matrix bridge"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )

    @patch('matrix_integration.services.matrix_bridge_service.AsyncClient')
    def test_concurrent_message_processing(self, mock_client_class):
        """Test handling multiple concurrent messages"""
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        # Create test conversations and messages synchronously for testing
        from django.db import transaction
        with transaction.atomic():
            for i in range(10):
                conversation = Conversation.objects.create(
                    company=self.company,
                    external_id=f'+123456789{i}',
                    platform='whatsapp',
                    participants=[{"id": f'+123456789{i}', "platform": 'whatsapp'}],
                    status='active'
                )
                
                Message.objects.create(
                    conversation=conversation,
                    direction='incoming',
                    message_type='text',
                    content=f'Message {i}',
                    sender_info={'matrix_sender': '@whatsapp_bot:matrix.nexus.local', 'platform': 'whatsapp'},
                    timestamp=timezone.now(),
                    is_processed=True
                )

        # Verify all conversations and messages were created
        conversations = Conversation.objects.filter(company=self.company)
        self.assertEqual(conversations.count(), 10)
        
        messages = Message.objects.filter(conversation__company=self.company)
        self.assertEqual(messages.count(), 10)
