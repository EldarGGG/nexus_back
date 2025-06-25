"""
Comprehensive unit tests for messaging services (WhatsApp, Telegram, Instagram, AI)
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock, Mock
import json
from datetime import datetime, timedelta

from messaging.models import Conversation, Message
from messaging.services.whatsapp_service import WhatsAppService
from messaging.services.telegram_service import TelegramService
from messaging.services.instagram_service import InstagramService
from messaging.services.ai_service import AIService
from companies.models import Company

User = get_user_model()


class WhatsAppServiceTest(TestCase):
    """Comprehensive tests for WhatsApp service"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.service = WhatsAppService()

    @patch('messaging.services.whatsapp_service.requests.post')
    def test_send_text_message_success(self, mock_post):
        """Test successful text message sending"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messages": [{"id": "msg_123"}]
        }
        mock_post.return_value = mock_response

        result = self.service.send_message(
            phone_number="+1234567890",
            message="Hello World",
            company_id=str(self.company.id),
            message_type="text"
        )

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["message_id"], "msg_123")
        mock_post.assert_called_once()

    @patch('messaging.services.whatsapp_service.requests.post')
    def test_send_text_message_failure(self, mock_post):
        """Test failed text message sending"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid phone number"
        mock_post.return_value = mock_response

        result = self.service.send_message(
            phone_number="invalid",
            message="Hello World",
            company_id=str(self.company.id)
        )

        self.assertEqual(result["status"], "failed")
        self.assertIn("Invalid phone number", result["error"])

    @patch('messaging.services.whatsapp_service.requests.post')
    def test_send_image_message(self, mock_post):
        """Test sending image message"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messages": [{"id": "img_123"}]
        }
        mock_post.return_value = mock_response

        result = self.service.send_message(
            phone_number="+1234567890",
            message="Check this out!",
            company_id=str(self.company.id),
            message_type="image",
            media_url="https://example.com/image.jpg"
        )

        self.assertEqual(result["status"], "sent")
        # Check that payload included image data
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload["type"], "image")
        self.assertIn("image", payload)

    @patch('messaging.services.whatsapp_service.requests.post')
    def test_send_document_message(self, mock_post):
        """Test sending document message"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messages": [{"id": "doc_123"}]
        }
        mock_post.return_value = mock_response

        result = self.service.send_message(
            phone_number="+1234567890",
            message="Here's the document",
            company_id=str(self.company.id),
            message_type="document",
            media_url="https://example.com/doc.pdf"
        )

        self.assertEqual(result["status"], "sent")
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload["type"], "document")

    def test_register_webhook_success(self):
        """Test successful webhook registration"""
        result = self.service.register_webhook(
            webhook_url="https://example.com/webhook",
            verify_token="verify_123"
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["webhook_url"], "https://example.com/webhook")

    @patch('messaging.services.whatsapp_service.Company.objects.get')
    def test_process_webhook_text_message(self, mock_company_get):
        """Test processing incoming text message webhook"""
        mock_company_get.return_value = self.company

        webhook_data = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": "msg_456",
                            "from": "+1234567890",
                            "timestamp": "1678901234",
                            "text": {"body": "Hello there!"}
                        }]
                    }
                }]
            }]
        }

        result = self.service.process_webhook(webhook_data, str(self.company.id))

        self.assertEqual(result["status"], "processed")
        # Check that conversation and message were created
        conversation = Conversation.objects.filter(
            company=self.company,
            external_id="+1234567890",
            platform="whatsapp"
        ).first()
        self.assertIsNotNone(conversation)

        message = Message.objects.filter(
            conversation=conversation,
            content="Hello there!"
        ).first()
        self.assertIsNotNone(message)
        self.assertEqual(message.direction, "incoming")

    @patch('messaging.services.whatsapp_service.Company.objects.get')
    def test_process_webhook_image_message(self, mock_company_get):
        """Test processing incoming image message webhook"""
        mock_company_get.return_value = self.company

        webhook_data = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "id": "img_456",
                            "from": "+1234567890",
                            "timestamp": "1678901234",
                            "image": {
                                "id": "image_id_123",
                                "caption": "Check this out!"
                            }
                        }]
                    }
                }]
            }]
        }

        result = self.service.process_webhook(webhook_data, str(self.company.id))

        self.assertEqual(result["status"], "processed")
        message = Message.objects.filter(
            conversation__company=self.company,
            content="Check this out!"
        ).first()
        self.assertIsNotNone(message)
        self.assertEqual(message.message_type, "image")
        self.assertEqual(len(message.attachments), 1)
        self.assertEqual(message.attachments[0]["type"], "image")

    def test_process_webhook_exception_handling(self):
        """Test webhook processing with invalid data"""
        invalid_data = {"invalid": "data"}
        
        result = self.service.process_webhook(invalid_data, str(self.company.id))
        
        self.assertEqual(result["status"], "failed")
        self.assertIn("error", result)

    @patch('messaging.services.whatsapp_service.requests.post')
    def test_send_message_network_exception(self, mock_post):
        """Test network exception handling"""
        mock_post.side_effect = Exception("Network error")

        result = self.service.send_message(
            phone_number="+1234567890",
            message="Hello",
            company_id=str(self.company.id)
        )

        self.assertEqual(result["status"], "failed")
        self.assertIn("Network error", result["error"])


class TelegramServiceTest(TestCase):
    """Comprehensive tests for Telegram service"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.service = TelegramService()

    @patch('messaging.services.telegram_service.requests.post')
    def test_send_message_success(self, mock_post):
        """Test successful message sending"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 123}
        }
        mock_post.return_value = mock_response

        result = self.service.send_message(
            chat_id="123456789",
            message="Hello Telegram!",
            company_id=str(self.company.id)
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["message_id"], 123)

    @patch('messaging.services.telegram_service.requests.post')
    def test_send_message_with_reply_markup(self, mock_post):
        """Test sending message with inline keyboard"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        reply_markup = {
            "inline_keyboard": [[
                {"text": "Yes", "callback_data": "yes"},
                {"text": "No", "callback_data": "no"}
            ]]
        }

        self.service.send_message(
            chat_id="123456789",
            message="Do you agree?",
            company_id=str(self.company.id),
            reply_markup=reply_markup
        )

        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertIn('reply_markup', payload)
        self.assertEqual(payload['reply_markup'], reply_markup)

    @patch('messaging.services.telegram_service.requests.post')
    def test_send_photo_success(self, mock_post):
        """Test successful photo sending"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        result = self.service.send_photo(
            chat_id="123456789",
            photo_url="https://example.com/photo.jpg",
            caption="Nice photo!"
        )

        self.assertTrue(result["ok"])
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload["photo"], "https://example.com/photo.jpg")
        self.assertEqual(payload["caption"], "Nice photo!")

    @patch('messaging.services.telegram_service.requests.post')
    def test_send_document_success(self, mock_post):
        """Test successful document sending"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        result = self.service.send_document(
            chat_id="123456789",
            document_url="https://example.com/doc.pdf",
            caption="Important document"
        )

        self.assertTrue(result["ok"])

    @patch('messaging.services.telegram_service.requests.post')
    def test_set_webhook_success(self, mock_post):
        """Test successful webhook setting"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        result = self.service.set_webhook("https://example.com/webhook")

        self.assertTrue(result["ok"])
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload["url"], "https://example.com/webhook")
        self.assertIn("allowed_updates", payload)

    @patch('messaging.services.telegram_service.Company.objects.get')
    def test_process_webhook_message(self, mock_company_get):
        """Test processing incoming message webhook"""
        mock_company_get.return_value = self.company

        webhook_data = {
            "message": {
                "message_id": 456,
                "chat": {"id": 123456789},
                "from": {
                    "id": 987654321,
                    "username": "testuser",
                    "first_name": "John"
                },
                "date": 1678901234,
                "text": "Hello bot!"
            }
        }

        result = self.service.process_webhook(webhook_data, str(self.company.id))

        self.assertEqual(result["status"], "processed")
        conversation = Conversation.objects.filter(
            company=self.company,
            external_id="123456789",
            platform="telegram"
        ).first()
        self.assertIsNotNone(conversation)

    @patch('messaging.services.telegram_service.Company.objects.get')
    def test_process_webhook_callback_query(self, mock_company_get):
        """Test processing callback query webhook"""
        mock_company_get.return_value = self.company

        webhook_data = {
            "callback_query": {
                "id": "callback_123",
                "from": {"id": 987654321, "username": "testuser"},
                "message": {
                    "message_id": 456,
                    "chat": {"id": 123456789}
                },
                "data": "button_clicked"
            }
        }

        result = self.service.process_webhook(webhook_data, str(self.company.id))

        self.assertEqual(result["status"], "processed")

    @patch('messaging.services.telegram_service.requests.post')
    def test_api_error_handling(self, mock_post):
        """Test API error handling"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        result = self.service.send_message(
            chat_id="invalid",
            message="Hello",
            company_id=str(self.company.id)
        )

        self.assertFalse(result["ok"])
        self.assertIn("Bad Request", result["error"])


class InstagramServiceTest(TestCase):
    """Comprehensive tests for Instagram service"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.service = InstagramService()

    @patch('messaging.services.instagram_service.requests.post')
    def test_send_message_success(self, mock_post):
        """Test successful message sending"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message_id": "mid.123456"
        }
        mock_post.return_value = mock_response

        result = self.service.send_message(
            recipient_id="123456789",
            message="Hello Instagram!",
            company_id=str(self.company.id)
        )

        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["message_id"], "mid.123456")

    @patch('messaging.services.instagram_service.requests.post')
    def test_send_image_message(self, mock_post):
        """Test sending image message"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message_id": "mid.img123"}
        mock_post.return_value = mock_response

        result = self.service.send_message(
            recipient_id="123456789",
            message="Check this image!",
            company_id=str(self.company.id),
            message_type="image",
            attachment_url="https://example.com/image.jpg"
        )

        self.assertEqual(result["status"], "sent")
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertIn("attachment", payload["message"])

    @patch('messaging.services.instagram_service.requests.post')
    def test_register_webhook_success(self, mock_post):
        """Test successful webhook registration"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_post.return_value = mock_response

        result = self.service.register_webhook(
            webhook_url="https://example.com/webhook",
            verify_token="verify_123"
        )

        self.assertEqual(result["status"], "success")

    @patch('messaging.services.instagram_service.Company.objects.get')
    def test_process_webhook_message(self, mock_company_get):
        """Test processing incoming message webhook"""
        mock_company_get.return_value = self.company

        webhook_data = {
            "entry": [{
                "messaging": [{
                    "sender": {"id": "123456789"},
                    "recipient": {"id": "987654321"},
                    "timestamp": 1678901234000,
                    "message": {
                        "mid": "mid.456",
                        "text": "Hello Instagram!"
                    }
                }]
            }]
        }

        result = self.service.process_webhook(webhook_data, str(self.company.id))

        self.assertEqual(result["status"], "processed")
        conversation = Conversation.objects.filter(
            company=self.company,
            external_id="123456789",
            platform="instagram"
        ).first()
        self.assertIsNotNone(conversation)

    @patch('messaging.services.instagram_service.requests.post')
    def test_api_error_handling(self, mock_post):
        """Test API error handling"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Invalid recipient"
        mock_post.return_value = mock_response

        result = self.service.send_message(
            recipient_id="invalid",
            message="Hello",
            company_id=str(self.company.id)
        )

        self.assertEqual(result["status"], "failed")
        self.assertIn("Invalid recipient", result["error"])


class AIServiceTest(TestCase):
    """Comprehensive tests for AI service"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.service = AIService()

    @patch('messaging.services.ai_service.genai')
    def test_generate_response_success(self, mock_genai):
        """Test successful AI response generation"""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = '''
        {
            "response": "Thank you for contacting us! How can I help you today?",
            "confidence": 0.95,
            "intent": "greeting",
            "suggested_actions": [],
            "requires_human": false
        }
        '''
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        # Reinitialize service to use mocked model
        with patch('messaging.services.ai_service.genai.configure'):
            service = AIService()
            service.model = mock_model

        result = service.generate_response(
            message="Hello there!",
            conversation_history=[],
            company_context={"name": "Test Company"}
        )

        self.assertIn("response", result)
        self.assertEqual(result["intent"], "greeting")
        self.assertGreater(result["confidence"], 0.9)

    @patch('messaging.services.ai_service.genai')
    def test_analyze_intent_success(self, mock_genai):
        """Test successful intent analysis"""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = '''
        {
            "intent": "complaint",
            "confidence": 0.85,
            "keywords": ["problem", "broken", "issue"]
        }
        '''
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        with patch('messaging.services.ai_service.genai.configure'):
            service = AIService()
            service.model = mock_model

        result = service.analyze_intent("I have a problem with my order, it's broken!")

        self.assertEqual(result["intent"], "complaint")
        self.assertEqual(result["confidence"], 0.85)
        self.assertIn("keywords", result)

    def test_analyze_intent_no_model(self):
        """Test intent analysis when no model is available"""
        service = AIService()
        service.model = None

        result = service.analyze_intent("Hello")

        self.assertEqual(result["intent"], "unknown")
        self.assertEqual(result["confidence"], 0.0)

    @patch('messaging.services.ai_service.genai')
    def test_generate_response_no_model(self, mock_genai):
        """Test response generation when no model is available"""
        service = AIService()
        service.model = None

        result = service.generate_response(
            message="Hello",
            conversation_history=[],
            company_context={}
        )

        self.assertEqual(result["intent"], "unknown")
        self.assertEqual(result["confidence"], 0.0)
        self.assertIn("AI service not available", result["response"])

    @patch('messaging.services.ai_service.genai')
    def test_generate_response_exception_handling(self, mock_genai):
        """Test exception handling in response generation"""
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("API Error")
        mock_genai.GenerativeModel.return_value = mock_model

        with patch('messaging.services.ai_service.genai.configure'):
            service = AIService()
            service.model = mock_model

        result = service.generate_response(
            message="Hello",
            conversation_history=[],
            company_context={}
        )

        self.assertEqual(result["intent"], "error")
        self.assertEqual(result["confidence"], 0.0)
        self.assertIn("error", result)

    @patch('messaging.services.ai_service.genai')
    def test_extract_entities_success(self, mock_genai):
        """Test successful entity extraction"""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = '''
        {
            "entities": [
                {"type": "PERSON", "value": "John Smith", "confidence": 0.9},
                {"type": "DATE", "value": "tomorrow", "confidence": 0.8}
            ]
        }
        '''
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        with patch('messaging.services.ai_service.genai.configure'):
            service = AIService()
            service.model = mock_model

        result = service.extract_entities("I need to book an appointment with John Smith for tomorrow")

        self.assertIn("entities", result)
        self.assertEqual(len(result["entities"]), 2)
        self.assertEqual(result["entities"][0]["type"], "PERSON")

    @patch('messaging.services.ai_service.genai')
    def test_sentiment_analysis_success(self, mock_genai):
        """Test successful sentiment analysis"""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = '''
        {
            "sentiment": "negative",
            "confidence": 0.9,
            "emotions": ["frustrated", "angry"]
        }
        '''
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        with patch('messaging.services.ai_service.genai.configure'):
            service = AIService()
            service.model = mock_model

        result = service.analyze_sentiment("I'm really frustrated with this service!")

        self.assertEqual(result["sentiment"], "negative")
        self.assertGreater(result["confidence"], 0.8)
        self.assertIn("emotions", result)

    def test_build_context_formatting(self):
        """Test context building for AI prompts"""
        service = AIService()
        
        company_context = {
            "name": "Test Corp",
            "industry": "Technology",
            "support_hours": "9 AM - 5 PM"
        }
        
        conversation_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there! How can I help?"}
        ]
        
        context = service._build_context(company_context, conversation_history)
        
        self.assertIn("Test Corp", context)
        self.assertIn("Technology", context)
        self.assertIn("Hello", context)

    @patch('messaging.services.ai_service.genai')
    def test_malformed_json_response_handling(self, mock_genai):
        """Test handling of malformed JSON responses from AI"""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "This is not valid JSON"
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        with patch('messaging.services.ai_service.genai.configure'):
            service = AIService()
            service.model = mock_model

        result = service.analyze_intent("Hello")

        # Should return the original text when no JSON braces are found
        self.assertEqual(result, "This is not valid JSON")
