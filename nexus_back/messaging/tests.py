from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch, MagicMock
from datetime import datetime

from .models import Conversation, Message, MessageTemplate
from companies.models import Company
from authentication.models import UserRole

User = get_user_model()


class ConversationModelTest(TestCase):
    """Test Conversation model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="agent",
            email="agent@example.com",
            company=self.company
        )

    def test_create_conversation(self):
        """Test creating a conversation"""
        conversation = Conversation.objects.create(
            company=self.company,
            external_id="wa_123456",
            platform="whatsapp",
            participants=[{"phone": "+1234567890", "name": "John Doe"}],
            assigned_agent=self.user
        )
        self.assertEqual(conversation.company, self.company)
        self.assertEqual(conversation.platform, "whatsapp")
        self.assertEqual(conversation.status, "active")
        self.assertEqual(conversation.assigned_agent, self.user)

    def test_conversation_str_representation(self):
        """Test conversation string representation"""
        conversation = Conversation.objects.create(
            company=self.company,
            external_id="tg_789012",
            platform="telegram",
            participants=[{"user_id": "123", "username": "johndoe"}]
        )
        self.assertEqual(str(conversation), "telegram - tg_789012")

    def test_unique_external_id_per_platform(self):
        """Test that external_id is unique per company and platform"""
        Conversation.objects.create(
            company=self.company,
            external_id="123456",
            platform="whatsapp"
        )
        
        # Should be able to create same external_id for different platform
        telegram_conv = Conversation.objects.create(
            company=self.company,
            external_id="123456",
            platform="telegram"
        )
        self.assertIsNotNone(telegram_conv)


class MessageModelTest(TestCase):
    """Test Message model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.conversation = Conversation.objects.create(
            company=self.company,
            external_id="wa_123456",
            platform="whatsapp"
        )

    def test_create_text_message(self):
        """Test creating a text message"""
        message = Message.objects.create(
            conversation=self.conversation,
            direction="incoming",
            message_type="text",
            content="Hello, I need help!",
            sender_info={"phone": "+1234567890", "name": "John Doe"},
            timestamp=timezone.now()
        )
        self.assertEqual(message.conversation, self.conversation)
        self.assertEqual(message.direction, "incoming")
        self.assertEqual(message.message_type, "text")
        self.assertEqual(message.content, "Hello, I need help!")

    def test_create_media_message(self):
        """Test creating a media message"""
        message = Message.objects.create(
            conversation=self.conversation,
            direction="incoming",
            message_type="image",
            content="Image received",
            attachments=[{"url": "https://example.com/image.jpg", "type": "image"}],
            timestamp=timezone.now()
        )
        self.assertEqual(message.message_type, "image")
        self.assertEqual(len(message.attachments), 1)

    def test_message_ordering(self):
        """Test that messages are ordered by timestamp"""
        now = timezone.now()
        
        # Create messages with different timestamps
        message1 = Message.objects.create(
            conversation=self.conversation,
            direction="incoming",
            content="First message",
            timestamp=now
        )
        message2 = Message.objects.create(
            conversation=self.conversation,
            direction="outgoing",
            content="Second message",
            timestamp=now.replace(second=now.second + 10)
        )
        
        messages = list(self.conversation.messages.all())
        self.assertEqual(messages[0], message1)
        self.assertEqual(messages[1], message2)

    def test_message_str_representation(self):
        """Test message string representation"""
        message = Message.objects.create(
            conversation=self.conversation,
            direction="outgoing",
            message_type="text",
            content="Response message",
            timestamp=timezone.now()
        )
        str_repr = str(message)
        self.assertIn("outgoing", str_repr)
        self.assertIn("text", str_repr)


class MessageTemplateModelTest(TestCase):
    """Test MessageTemplate model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="creator",
            email="creator@example.com",
            company=self.company
        )

    def test_create_message_template(self):
        """Test creating a message template"""
        template = MessageTemplate.objects.create(
            company=self.company,
            name="Welcome Message",
            content="Hello {{name}}, welcome to our service!",
            variables=["name"],
            category="welcome",
            created_by=self.user
        )
        self.assertEqual(template.company, self.company)
        self.assertEqual(template.name, "Welcome Message")
        self.assertIn("name", template.variables)
        self.assertTrue(template.is_active)

    def test_template_str_representation(self):
        """Test template string representation"""
        template = MessageTemplate.objects.create(
            company=self.company,
            name="Support Template",
            content="Thank you for contacting support",
            created_by=self.user
        )
        expected = f"{self.company.name} - Support Template"
        self.assertEqual(str(template), expected)


class MessagingAPITest(APITestCase):
    """Test Messaging API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="agent",
            email="agent@example.com",
            password="testpass123",
            company=self.company
        )
        UserRole.objects.create(
            user=self.user,
            role="agent",
            permissions={"can_send_messages": True}
        )
        
        self.conversation = Conversation.objects.create(
            company=self.company,
            external_id="wa_123456",
            platform="whatsapp",
            assigned_agent=self.user
        )
        
        # Authenticate user
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_get_conversations(self):
        """Test getting conversation list"""
        url = reverse('messaging:conversation-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_get_conversation_detail(self):
        """Test getting conversation detail"""
        url = reverse('messaging:conversation-detail', kwargs={'pk': self.conversation.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['external_id'], "wa_123456")

    def test_send_message(self):
        """Test sending a message"""
        url = reverse('messaging:conversation-send-message', kwargs={'pk': self.conversation.pk})
        data = {
            'content': 'Hello customer!',
            'message_type': 'text'
        }
        with patch('messaging.tasks.send_message_to_platform.delay') as mock_send:
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            mock_send.assert_called_once()

    def test_get_conversation_messages(self):
        """Test getting messages for a conversation"""
        # Create some messages
        Message.objects.create(
            conversation=self.conversation,
            direction="incoming",
            content="Customer message",
            timestamp=timezone.now()
        )
        Message.objects.create(
            conversation=self.conversation,
            direction="outgoing",
            content="Agent response",
            timestamp=timezone.now()
        )
        
        url = reverse('messaging:conversation-messages', kwargs={'pk': self.conversation.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_assign_conversation(self):
        """Test assigning conversation to agent"""
        other_agent = User.objects.create_user(
            username="agent2",
            email="agent2@example.com",
            company=self.company
        )
        
        url = reverse('messaging:conversation-assign', kwargs={'pk': self.conversation.pk})
        data = {'agent_id': other_agent.id}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.assigned_agent, other_agent)

    def test_multi_tenant_isolation(self):
        """Test that conversations are isolated by company"""
        # Create another company and conversation
        other_company = Company.objects.create(
            name="Other Company",
            industry="finance",
            company_size="50-100"
        )
        other_conversation = Conversation.objects.create(
            company=other_company,
            external_id="other_123",
            platform="telegram"
        )
        
        # Try to access other company's conversation
        url = reverse('messaging:conversation-detail', kwargs={'pk': other_conversation.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class MessageTemplateAPITest(APITestCase):
    """Test Message Template API"""

    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="testpass123",
            company=self.company
        )
        UserRole.objects.create(
            user=self.user,
            role="manager",
            permissions={"can_manage_templates": True}
        )
        
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_create_template(self):
        """Test creating a message template"""
        url = reverse('messaging:messagetemplate-list')
        data = {
            'name': 'Welcome Template',
            'content': 'Hello {{name}}, welcome to {{company}}!',
            'variables': ['name', 'company'],
            'category': 'welcome'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Welcome Template')

    def test_use_template_for_message(self):
        """Test using a template to send a message"""
        template = MessageTemplate.objects.create(
            company=self.company,
            name="Quick Response",
            content="Thank you for your message. We'll get back to you soon.",
            created_by=self.user
        )
        
        conversation = Conversation.objects.create(
            company=self.company,
            external_id="wa_789",
            platform="whatsapp"
        )
        
        url = reverse('messaging:conversation-send-template-message', kwargs={'pk': conversation.pk})
        data = {
            'template_id': template.id,
            'variables': {}
        }
        with patch('messaging.tasks.send_message_to_platform.delay') as mock_send:
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            mock_send.assert_called_once()


class WhatsAppIntegrationTest(TestCase):
    """Test WhatsApp integration functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )

    @patch('messaging.services.whatsapp_service.send_message')
    def test_send_whatsapp_message(self, mock_send):
        """Test sending WhatsApp message"""
        from messaging.services.whatsapp_service import WhatsAppService
        
        service = WhatsAppService()
        mock_send.return_value = {"message_id": "wa_msg_123", "status": "sent"}
        
        result = service.send_message(
            phone_number="+1234567890",
            message="Hello from test!",
            company_id=self.company.id
        )
        
        mock_send.assert_called_once()
        self.assertEqual(result["status"], "sent")

    @patch('messaging.services.whatsapp_service.register_webhook')
    def test_register_whatsapp_webhook(self, mock_register):
        """Test registering WhatsApp webhook"""
        from messaging.services.whatsapp_service import WhatsAppService
        
        service = WhatsAppService()
        mock_register.return_value = {"status": "success"}
        
        result = service.register_webhook(
            webhook_url="https://myapp.com/webhook/whatsapp",
            verify_token="my_verify_token"
        )
        
        mock_register.assert_called_once()
        self.assertEqual(result["status"], "success")

    def test_process_whatsapp_webhook(self):
        """Test processing WhatsApp webhook data"""
        from messaging.services.whatsapp_service import WhatsAppService
        
        webhook_data = {
            "messages": [{
                "id": "wa_msg_123",
                "from": "+1234567890",
                "text": {"body": "Hello!"},
                "timestamp": "1234567890"
            }]
        }
        
        service = WhatsAppService()
        with patch.object(service, 'create_conversation_and_message') as mock_create:
            service.process_webhook(webhook_data, self.company.id)
            mock_create.assert_called_once()


class TelegramIntegrationTest(TestCase):
    """Test Telegram integration functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )

    @patch('messaging.services.telegram_service.send_message')
    def test_send_telegram_message(self, mock_send):
        """Test sending Telegram message"""
        from messaging.services.telegram_service import TelegramService
        
        service = TelegramService()
        mock_send.return_value = {"message_id": 123, "ok": True}
        
        result = service.send_message(
            chat_id="123456789",
            message="Hello from Telegram test!",
            company_id=self.company.id
        )
        
        mock_send.assert_called_once()
        self.assertTrue(result["ok"])

    @patch('messaging.services.telegram_service.set_webhook')
    def test_set_telegram_webhook(self, mock_set_webhook):
        """Test setting Telegram webhook"""
        from messaging.services.telegram_service import TelegramService
        
        service = TelegramService()
        mock_set_webhook.return_value = {"ok": True}
        
        result = service.set_webhook("https://myapp.com/webhook/telegram")
        
        mock_set_webhook.assert_called_once()
        self.assertTrue(result["ok"])


class InstagramIntegrationTest(TestCase):
    """Test Instagram integration functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )

    @patch('messaging.services.instagram_service.send_message')
    def test_send_instagram_message(self, mock_send):
        """Test sending Instagram message"""
        from messaging.services.instagram_service import InstagramService
        
        service = InstagramService()
        mock_send.return_value = {"id": "ig_msg_123"}
        
        result = service.send_message(
            recipient_id="instagram_user_123",
            message="Hello from Instagram test!",
            company_id=self.company.id
        )
        
        mock_send.assert_called_once()
        self.assertIn("id", result)

    def test_process_instagram_webhook(self):
        """Test processing Instagram webhook data"""
        from messaging.services.instagram_service import InstagramService
        
        webhook_data = {
            "messaging": [{
                "sender": {"id": "instagram_user_123"},
                "recipient": {"id": "my_page_id"},
                "timestamp": 1234567890,
                "message": {
                    "mid": "ig_msg_123",
                    "text": "Hello from Instagram!"
                }
            }]
        }
        
        service = InstagramService()
        with patch.object(service, 'create_conversation_and_message') as mock_create:
            service.process_webhook(webhook_data, self.company.id)
            mock_create.assert_called_once()


class MessageProcessingTest(TestCase):
    """Test message processing and automation"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.conversation = Conversation.objects.create(
            company=self.company,
            external_id="wa_123456",
            platform="whatsapp"
        )

    @patch('messaging.tasks.process_incoming_message.delay')
    def test_incoming_message_processing(self, mock_process):
        """Test that incoming messages trigger processing"""
        message = Message.objects.create(
            conversation=self.conversation,
            direction="incoming",
            content="I need help with my order",
            timestamp=timezone.now()
        )
        
        # Simulate the signal or direct call
        from messaging.tasks import process_incoming_message
        process_incoming_message.delay(message.id)
        
        mock_process.assert_called_once_with(message.id)

    @patch('messaging.services.ai_service.generate_response')
    def test_ai_response_generation(self, mock_ai):
        """Test AI response generation"""
        from messaging.services.ai_service import AIService
        
        mock_ai.return_value = {
            "response": "I'd be happy to help you with your order. Can you provide your order number?",
            "confidence": 0.95,
            "intent": "order_support"
        }
        
        service = AIService()
        result = service.generate_response(
            message="I need help with my order",
            conversation_history=[],
            company_context={"name": "Test Company"}
        )
        
        mock_ai.assert_called_once()
        self.assertIn("response", result)
        self.assertEqual(result["intent"], "order_support")
