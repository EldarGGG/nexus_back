"""
Bridge Configuration Tests - B2B Multi-tenant Bridge Setup
"""
import json
from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from companies.models import Company, CompanyBridgeConfiguration, CompanyBridgeWebhook
from authentication.models import UserRole

User = get_user_model()


class BridgeConfigurationModelTest(TestCase):
    """Test bridge configuration models"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )

    def test_create_bridge_configuration(self):
        """Test creating a bridge configuration"""
        config = CompanyBridgeConfiguration.objects.create(
            company=self.company,
            platform='whatsapp',
            status='pending',
            whatsapp_phone_number_id='123456789',
            whatsapp_business_account_id='987654321'
        )
        
        self.assertEqual(config.platform, 'whatsapp')
        self.assertEqual(config.status, 'pending')
        self.assertEqual(config.company, self.company)

    def test_encrypt_decrypt_config(self):
        """Test encryption and decryption of sensitive config data"""
        config = CompanyBridgeConfiguration.objects.create(
            company=self.company,
            platform='whatsapp',
            status='pending'
        )
        
        sensitive_data = {
            'access_token': 'secret_token_123',
            'webhook_verify_token': 'verify_token_456'
        }
        
        # Encrypt data
        config.set_encrypted_config(sensitive_data)
        self.assertIsNotNone(config.encrypted_config)
        
        # Decrypt data
        decrypted_data = config.get_decrypted_config()
        self.assertEqual(decrypted_data['access_token'], 'secret_token_123')
        self.assertEqual(decrypted_data['webhook_verify_token'], 'verify_token_456')

    def test_setup_instructions(self):
        """Test getting setup instructions for platforms"""
        config = CompanyBridgeConfiguration.objects.create(
            company=self.company,
            platform='telegram',
            status='pending'
        )
        
        instructions = config.get_setup_instructions()
        
        self.assertIn('title', instructions)
        self.assertIn('steps', instructions)
        self.assertIn('required_fields', instructions)
        self.assertIn('webhook_url', instructions)
        self.assertEqual(instructions['title'], 'Telegram Bot Setup')

    def test_unique_company_platform_constraint(self):
        """Test that each company can only have one config per platform"""
        CompanyBridgeConfiguration.objects.create(
            company=self.company,
            platform='whatsapp',
            status='pending'
        )
        
        # Try to create another WhatsApp config for same company
        with self.assertRaises(Exception):
            CompanyBridgeConfiguration.objects.create(
                company=self.company,
                platform='whatsapp',
                status='pending'
            )


class BridgeConfigurationAPITest(APITestCase):
    """Test bridge configuration API endpoints"""

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

    def test_get_platforms_status(self):
        """Test getting platform status overview"""
        url = '/api/bridge-configs/platforms/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('platforms', response.data)
        self.assertIn('company', response.data)
        
        # Check all platforms are listed
        platform_codes = [p['code'] for p in response.data['platforms']]
        expected_platforms = ['whatsapp', 'telegram', 'instagram', 'facebook', 'signal']
        for platform in expected_platforms:
            self.assertIn(platform, platform_codes)

    def test_setup_platform_bridge(self):
        """Test initializing platform bridge setup"""
        url = '/api/bridge-configs/setup/'
        data = {'platform': 'whatsapp'}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'setup_initialized')
        self.assertEqual(response.data['platform'], 'whatsapp')
        self.assertIn('instructions', response.data)
        self.assertIn('config_id', response.data)
        
        # Verify config was created
        config = CompanyBridgeConfiguration.objects.get(
            company=self.company,
            platform='whatsapp'
        )
        self.assertEqual(config.status, 'pending')

    def test_setup_invalid_platform(self):
        """Test setting up invalid platform"""
        url = '/api/bridge-configs/setup/'
        data = {'platform': 'invalid_platform'}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    @patch('companies.bridge_views.CompanyBridgeConfigurationViewSet._test_whatsapp_connection')
    def test_configure_whatsapp_bridge(self, mock_test):
        """Test configuring WhatsApp bridge"""
        # Create bridge config
        config = CompanyBridgeConfiguration.objects.create(
            company=self.company,
            platform='whatsapp',
            status='pending'
        )
        
        # Mock successful test
        mock_test.return_value = {'success': True, 'message': 'Test successful'}
        
        url = f'/api/bridge-configs/{config.id}/configure/'
        data = {
            'access_token': 'test_token_123',
            'phone_number_id': '123456789',
            'business_account_id': '987654321',
            'webhook_verify_token': 'verify_token_456'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'configured')
        
        # Verify config was updated
        config.refresh_from_db()
        self.assertEqual(config.status, 'configured')
        self.assertEqual(config.whatsapp_phone_number_id, '123456789')
        self.assertEqual(config.whatsapp_business_account_id, '987654321')
        
        # Verify sensitive data was encrypted
        self.assertIsNotNone(config.encrypted_config)
        decrypted = config.get_decrypted_config()
        self.assertEqual(decrypted['access_token'], 'test_token_123')

    def test_configure_telegram_bridge(self):
        """Test configuring Telegram bridge"""
        config = CompanyBridgeConfiguration.objects.create(
            company=self.company,
            platform='telegram',
            status='pending'
        )
        
        url = f'/api/bridge-configs/{config.id}/configure/'
        data = {
            'bot_token': 'test_bot_token_123',
            'bot_username': 'test_bot'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'configured')
        
        # Verify config was updated
        config.refresh_from_db()
        self.assertEqual(config.status, 'configured')
        self.assertEqual(config.telegram_bot_username, 'test_bot')

    @patch('companies.bridge_views.CompanyBridgeConfigurationViewSet._test_whatsapp_connection')
    @patch('matrix_integration.services.matrix_bridge_service.matrix_service.initialize_company_bridge')
    def test_test_bridge_connection(self, mock_matrix_init, mock_test):
        """Test testing bridge connection"""
        config = CompanyBridgeConfiguration.objects.create(
            company=self.company,
            platform='whatsapp',
            status='configured'
        )
        config.set_encrypted_config({
            'access_token': 'test_token',
            'phone_number_id': '123456789'
        })
        config.save()
        
        # Mock successful test and matrix initialization
        mock_test.return_value = {'success': True, 'message': 'Test successful'}
        mock_matrix_init.return_value = None
        
        url = f'/api/bridge-configs/{config.id}/test/'
        data = {
            'test_message': 'Hello from test',
            'skip_message_test': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'active')
        
        # Verify config was activated
        config.refresh_from_db()
        self.assertEqual(config.status, 'active')
        self.assertIsNotNone(config.setup_completed_at)

    def test_get_bridge_status(self):
        """Test getting detailed bridge status"""
        config = CompanyBridgeConfiguration.objects.create(
            company=self.company,
            platform='whatsapp',
            status='active'
        )
        
        # Create a webhook event
        CompanyBridgeWebhook.objects.create(
            bridge_config=config,
            event_type='message_received',
            event_data={'test': 'data'},
            processed=True
        )
        
        url = f'/api/bridge-configs/{config.id}/status/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['platform'], 'whatsapp')
        self.assertEqual(response.data['status'], 'active')
        self.assertIn('recent_events', response.data)
        self.assertEqual(len(response.data['recent_events']), 1)

    def test_deactivate_bridge(self):
        """Test deactivating a bridge"""
        config = CompanyBridgeConfiguration.objects.create(
            company=self.company,
            platform='whatsapp',
            status='active'
        )
        
        url = f'/api/bridge-configs/{config.id}/deactivate/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'inactive')
        
        # Verify config was deactivated
        config.refresh_from_db()
        self.assertEqual(config.status, 'inactive')

    def test_unauthorized_access(self):
        """Test that unauthorized users cannot access bridge configs"""
        # Create another company and user
        other_company = Company.objects.create(
            name="Other Company",
            industry="finance",
            size="medium"
        )
        config = CompanyBridgeConfiguration.objects.create(
            company=other_company,
            platform='whatsapp',
            status='active'
        )
        
        # Try to access other company's config
        url = f'/api/bridge-configs/{config.id}/status/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class BridgeConnectionTestCase(TestCase):
    """Test platform connection methods"""
    
    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.config = CompanyBridgeConfiguration.objects.create(
            company=self.company,
            platform='whatsapp',
            status='configured'
        )

    @patch('requests.get')
    def test_whatsapp_connection_success(self, mock_get):
        """Test successful WhatsApp API connection"""
        from companies.bridge_views import CompanyBridgeConfigurationViewSet
        
        # Mock successful API response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {'id': '123456789'}
        
        viewset = CompanyBridgeConfigurationViewSet()
        config_data = {
            'access_token': 'test_token',
            'phone_number_id': '123456789'
        }
        
        result = viewset._test_whatsapp_connection(config_data, {})
        
        self.assertTrue(result['success'])
        self.assertIn('WhatsApp API connection successful', result['message'])

    @patch('requests.get')
    def test_whatsapp_connection_failure(self, mock_get):
        """Test failed WhatsApp API connection"""
        from companies.bridge_views import CompanyBridgeConfigurationViewSet
        
        # Mock failed API response
        mock_get.return_value.status_code = 401
        mock_get.return_value.text = 'Invalid access token'
        
        viewset = CompanyBridgeConfigurationViewSet()
        config_data = {
            'access_token': 'invalid_token',
            'phone_number_id': '123456789'
        }
        
        result = viewset._test_whatsapp_connection(config_data, {})
        
        self.assertFalse(result['success'])
        self.assertIn('API test failed', result['error'])

    @patch('requests.get')
    def test_telegram_connection_success(self, mock_get):
        """Test successful Telegram bot connection"""
        from companies.bridge_views import CompanyBridgeConfigurationViewSet
        
        # Mock successful bot API response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            'ok': True,
            'result': {
                'id': 123456789,
                'username': 'test_bot',
                'first_name': 'Test Bot'
            }
        }
        
        viewset = CompanyBridgeConfigurationViewSet()
        config_data = {'bot_token': 'test_bot_token'}
        
        result = viewset._test_telegram_connection(config_data, {})
        
        self.assertTrue(result['success'])
        self.assertIn('Telegram bot connection successful', result['message'])
        self.assertIn('bot_info', result)
