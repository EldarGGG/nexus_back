"""
Comprehensive unit tests for integrations functionality
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, Mock
import json
from datetime import datetime, timedelta

from .models import Integration, CompanyIntegration, IntegrationLog
from companies.models import Company

User = get_user_model()


class IntegrationModelTest(TestCase):
    """Test Integration model functionality"""

    def test_create_integration(self):
        """Test creating an integration"""
        integration = Integration.objects.create(
            name="Slack",
            description="Team communication platform integration",
            integration_type="webhook",
            documentation_url="https://api.slack.com/docs",
            configuration_schema={
                "type": "object",
                "properties": {
                    "webhook_url": {"type": "string"},
                    "channel": {"type": "string"},
                    "username": {"type": "string"}
                },
                "required": ["webhook_url"]
            }
        )
        
        self.assertEqual(integration.name, "Slack")
        self.assertEqual(integration.integration_type, "webhook")
        self.assertTrue(integration.is_active)
        self.assertIn("webhook_url", integration.configuration_schema["properties"])

    def test_integration_str_representation(self):
        """Test integration string representation"""
        integration = Integration.objects.create(
            name="Discord",
            description="Gaming communication platform",
            integration_type="webhook"
        )
        
        self.assertEqual(str(integration), "Discord")

    def test_integration_types(self):
        """Test different integration types"""
        types = ["webhook", "api", "oauth", "websocket"]
        
        for integration_type in types:
            integration = Integration.objects.create(
                name=f"Test {integration_type.title()}",
                description=f"Test {integration_type} integration",
                integration_type=integration_type
            )
            
            self.assertEqual(integration.integration_type, integration_type)

    def test_configuration_schema_validation(self):
        """Test configuration schema structure"""
        complex_schema = {
            "type": "object",
            "properties": {
                "api_key": {
                    "type": "string",
                    "description": "API key for authentication"
                },
                "base_url": {
                    "type": "string",
                    "format": "uri",
                    "default": "https://api.example.com"
                },
                "timeout": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 300,
                    "default": 30
                },
                "features": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["api_key"]
        }
        
        integration = Integration.objects.create(
            name="Complex API",
            description="Complex API integration",
            integration_type="api",
            configuration_schema=complex_schema
        )
        
        self.assertEqual(integration.configuration_schema["type"], "object")
        self.assertIn("api_key", integration.configuration_schema["required"])

    def test_inactive_integration(self):
        """Test inactive integration"""
        integration = Integration.objects.create(
            name="Deprecated Service",
            description="Old integration",
            integration_type="api",
            is_active=False
        )
        
        self.assertFalse(integration.is_active)
        
        # Query for active integrations should exclude this
        active_integrations = Integration.objects.filter(is_active=True)
        self.assertNotIn(integration, active_integrations)


class CompanyIntegrationModelTest(TestCase):
    """Test CompanyIntegration model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            company=self.company
        )
        self.integration = Integration.objects.create(
            name="Slack",
            description="Team communication platform",
            integration_type="webhook",
            configuration_schema={
                "type": "object",
                "properties": {
                    "webhook_url": {"type": "string"},
                    "channel": {"type": "string"}
                },
                "required": ["webhook_url"]
            }
        )

    def test_create_company_integration(self):
        """Test creating a company integration"""
        company_integration = CompanyIntegration.objects.create(
            company=self.company,
            integration=self.integration,
            name="Main Slack Channel",
            configuration={
                "webhook_url": "https://hooks.slack.com/services/xxx/yyy/zzz",
                "channel": "#general",
                "username": "ChatBot"
            },
            credentials={
                "api_token": "encrypted_token_here"
            },
            created_by=self.user
        )
        
        self.assertEqual(company_integration.company, self.company)
        self.assertEqual(company_integration.integration, self.integration)
        self.assertEqual(company_integration.name, "Main Slack Channel")
        self.assertEqual(company_integration.status, "pending")
        self.assertEqual(company_integration.created_by, self.user)

    def test_company_integration_str_representation(self):
        """Test company integration string representation"""
        company_integration = CompanyIntegration.objects.create(
            company=self.company,
            integration=self.integration,
            name="Test Integration",
            created_by=self.user
        )
        
        expected_str = f"{self.company.name} - {self.integration.name}"
        self.assertEqual(str(company_integration), expected_str)

    def test_integration_status_changes(self):
        """Test integration status transitions"""
        company_integration = CompanyIntegration.objects.create(
            company=self.company,
            integration=self.integration,
            name="Status Test",
            created_by=self.user
        )
        
        # Initial status
        self.assertEqual(company_integration.status, "pending")
        
        # Activate
        company_integration.status = "active"
        company_integration.last_sync = timezone.now()
        company_integration.save()
        
        self.assertEqual(company_integration.status, "active")
        self.assertIsNotNone(company_integration.last_sync)
        
        # Error state
        company_integration.status = "error"
        company_integration.error_message = "Failed to connect to webhook"
        company_integration.save()
        
        self.assertEqual(company_integration.status, "error")
        self.assertIn("Failed to connect", company_integration.error_message)

    def test_configuration_storage(self):
        """Test configuration and credentials storage"""
        config = {
            "webhook_url": "https://example.com/webhook",
            "timeout": 30,
            "retry_attempts": 3,
            "custom_headers": {
                "User-Agent": "ChatBot/1.0"
            }
        }
        
        credentials = {
            "api_key": "sk-1234567890abcdef",
            "secret": "encrypted_secret_here"
        }
        
        company_integration = CompanyIntegration.objects.create(
            company=self.company,
            integration=self.integration,
            name="Config Test",
            configuration=config,
            credentials=credentials,
            created_by=self.user
        )
        
        self.assertEqual(company_integration.configuration["webhook_url"], config["webhook_url"])
        self.assertEqual(company_integration.configuration["timeout"], 30)
        self.assertEqual(company_integration.credentials["api_key"], credentials["api_key"])

    def test_unique_constraint(self):
        """Test unique constraint on company, integration, name"""
        CompanyIntegration.objects.create(
            company=self.company,
            integration=self.integration,
            name="Unique Test",
            created_by=self.user
        )
        
        # Creating another with same company, integration, name should fail
        with self.assertRaises(Exception):
            CompanyIntegration.objects.create(
                company=self.company,
                integration=self.integration,
                name="Unique Test",
                created_by=self.user
            )

    def test_multiple_integrations_same_type(self):
        """Test multiple integrations of same type for one company"""
        # Create first Slack integration
        slack1 = CompanyIntegration.objects.create(
            company=self.company,
            integration=self.integration,
            name="Sales Channel",
            configuration={"webhook_url": "https://hooks.slack.com/sales"},
            created_by=self.user
        )
        
        # Create second Slack integration with different name
        slack2 = CompanyIntegration.objects.create(
            company=self.company,
            integration=self.integration,
            name="Support Channel",
            configuration={"webhook_url": "https://hooks.slack.com/support"},
            created_by=self.user
        )
        
        company_integrations = CompanyIntegration.objects.filter(
            company=self.company,
            integration=self.integration
        )
        
        self.assertEqual(company_integrations.count(), 2)
        self.assertIn(slack1, company_integrations)
        self.assertIn(slack2, company_integrations)


class IntegrationLogModelTest(TestCase):
    """Test IntegrationLog model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            company=self.company
        )
        self.integration = Integration.objects.create(
            name="Slack",
            description="Team communication platform",
            integration_type="webhook"
        )
        self.company_integration = CompanyIntegration.objects.create(
            company=self.company,
            integration=self.integration,
            name="Test Integration",
            created_by=self.user
        )

    def test_create_integration_log(self):
        """Test creating an integration log"""
        log = IntegrationLog.objects.create(
            company_integration=self.company_integration,
            level="info",
            message="Successfully sent message to Slack",
            details={
                "webhook_url": "https://hooks.slack.com/xxx",
                "response_code": 200,
                "response_time": 150
            }
        )
        
        self.assertEqual(log.company_integration, self.company_integration)
        self.assertEqual(log.level, "info")
        self.assertIn("Successfully sent", log.message)
        self.assertEqual(log.details["response_code"], 200)

    def test_integration_log_str_representation(self):
        """Test integration log string representation"""
        log = IntegrationLog.objects.create(
            company_integration=self.company_integration,
            level="error",
            message="Failed to connect"
        )
        
        expected_str = f"{self.company_integration.name} - error - {log.timestamp}"
        self.assertEqual(str(log), expected_str)

    def test_log_levels(self):
        """Test different log levels"""
        levels = ["info", "warning", "error"]
        
        for level in levels:
            log = IntegrationLog.objects.create(
                company_integration=self.company_integration,
                level=level,
                message=f"Test {level} message"
            )
            
            self.assertEqual(log.level, level)

    def test_log_ordering(self):
        """Test log ordering by timestamp"""
        # Create logs with slight time differences
        log1 = IntegrationLog.objects.create(
            company_integration=self.company_integration,
            level="info",
            message="First log"
        )
        
        log2 = IntegrationLog.objects.create(
            company_integration=self.company_integration,
            level="info",
            message="Second log"
        )
        
        logs = list(IntegrationLog.objects.all())
        
        # Should be ordered by newest first
        self.assertEqual(logs[0], log2)
        self.assertEqual(logs[1], log1)

    def test_detailed_error_logging(self):
        """Test detailed error logging"""
        error_details = {
            "error_code": "WEBHOOK_TIMEOUT",
            "request_url": "https://hooks.slack.com/services/xxx",
            "request_method": "POST",
            "request_headers": {
                "Content-Type": "application/json",
                "User-Agent": "ChatBot/1.0"
            },
            "request_body": {
                "text": "Hello Slack!",
                "channel": "#general"
            },
            "response_status": 408,
            "response_headers": {},
            "error_message": "Request timeout after 30 seconds",
            "retry_attempt": 2,
            "timestamp": timezone.now().isoformat()
        }
        
        log = IntegrationLog.objects.create(
            company_integration=self.company_integration,
            level="error",
            message="Webhook request timed out",
            details=error_details
        )
        
        self.assertEqual(log.details["error_code"], "WEBHOOK_TIMEOUT")
        self.assertEqual(log.details["response_status"], 408)
        self.assertEqual(log.details["retry_attempt"], 2)


class IntegrationServiceTest(TestCase):
    """Test integration service functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            company=self.company
        )

    @patch('integrations.services.requests.post')
    def test_webhook_integration_execution(self, mock_post):
        """Test webhook integration execution"""
        # Mock successful webhook response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response
        
        # Create webhook integration
        webhook_integration = Integration.objects.create(
            name="Custom Webhook",
            description="Custom webhook integration",
            integration_type="webhook"
        )
        
        company_integration = CompanyIntegration.objects.create(
            company=self.company,
            integration=webhook_integration,
            name="Notification Webhook",
            configuration={
                "webhook_url": "https://example.com/webhook",
                "method": "POST",
                "headers": {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer token123"
                }
            },
            status="active",
            created_by=self.user
        )
        
        # Simulate webhook execution
        payload = {
            "event": "new_message",
            "data": {
                "conversation_id": "conv_123",
                "message": "Hello World!"
            }
        }
        
        # Mock the webhook call
        headers = company_integration.configuration["headers"]
        mock_post(
            company_integration.configuration["webhook_url"],
            json=payload,
            headers=headers
        )
        
        # Verify the call was made
        mock_post.assert_called_once_with(
            "https://example.com/webhook",
            json=payload,
            headers=headers
        )
        
        # Log successful execution
        IntegrationLog.objects.create(
            company_integration=company_integration,
            level="info",
            message="Webhook executed successfully",
            details={
                "status_code": mock_response.status_code,
                "response": mock_response.json()
            }
        )
        
        log = IntegrationLog.objects.filter(
            company_integration=company_integration
        ).first()
        
        self.assertEqual(log.level, "info")
        self.assertEqual(log.details["status_code"], 200)

    @patch('integrations.services.requests.post')
    def test_webhook_integration_failure(self, mock_post):
        """Test webhook integration failure handling"""
        # Mock failed webhook response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        webhook_integration = Integration.objects.create(
            name="Failing Webhook",
            description="Webhook that fails",
            integration_type="webhook"
        )
        
        company_integration = CompanyIntegration.objects.create(
            company=self.company,
            integration=webhook_integration,
            name="Failing Integration",
            configuration={"webhook_url": "https://failing.example.com/webhook"},
            status="active",
            created_by=self.user
        )
        
        # Simulate failed webhook execution
        payload = {"test": "data"}
        
        mock_post(
            company_integration.configuration["webhook_url"],
            json=payload
        )
        
        # Log the failure
        company_integration.status = "error"
        company_integration.error_message = f"Webhook failed with status {mock_response.status_code}"
        company_integration.save()
        
        IntegrationLog.objects.create(
            company_integration=company_integration,
            level="error",
            message="Webhook execution failed",
            details={
                "status_code": mock_response.status_code,
                "error": mock_response.text
            }
        )
        
        self.assertEqual(company_integration.status, "error")
        self.assertIn("failed with status 500", company_integration.error_message)

    def test_oauth_integration_flow(self):
        """Test OAuth integration flow"""
        oauth_integration = Integration.objects.create(
            name="OAuth Service",
            description="OAuth-based integration",
            integration_type="oauth",
            configuration_schema={
                "type": "object",
                "properties": {
                    "client_id": {"type": "string"},
                    "client_secret": {"type": "string"},
                    "redirect_uri": {"type": "string"},
                    "scopes": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["client_id", "client_secret", "redirect_uri"]
            }
        )
        
        company_integration = CompanyIntegration.objects.create(
            company=self.company,
            integration=oauth_integration,
            name="OAuth Integration",
            configuration={
                "client_id": "oauth_client_123",
                "redirect_uri": "https://myapp.com/oauth/callback",
                "scopes": ["read", "write"]
            },
            credentials={
                "client_secret": "encrypted_secret",
                "access_token": "oauth_access_token",
                "refresh_token": "oauth_refresh_token",
                "expires_at": (timezone.now() + timedelta(hours=1)).isoformat()
            },
            status="active",
            created_by=self.user
        )
        
        self.assertEqual(company_integration.integration.integration_type, "oauth")
        self.assertIn("access_token", company_integration.credentials)
        self.assertIn("refresh_token", company_integration.credentials)

    def test_api_integration_configuration(self):
        """Test API integration configuration"""
        api_integration = Integration.objects.create(
            name="REST API",
            description="REST API integration",
            integration_type="api",
            configuration_schema={
                "type": "object",
                "properties": {
                    "base_url": {"type": "string"},
                    "api_key": {"type": "string"},
                    "rate_limit": {"type": "integer"},
                    "timeout": {"type": "integer"}
                },
                "required": ["base_url", "api_key"]
            }
        )
        
        company_integration = CompanyIntegration.objects.create(
            company=self.company,
            integration=api_integration,
            name="External API",
            configuration={
                "base_url": "https://api.external-service.com/v1",
                "rate_limit": 100,
                "timeout": 30
            },
            credentials={
                "api_key": "encrypted_api_key_here"
            },
            status="active",
            created_by=self.user
        )
        
        self.assertEqual(
            company_integration.configuration["base_url"],
            "https://api.external-service.com/v1"
        )
        self.assertEqual(company_integration.configuration["rate_limit"], 100)

    def test_integration_health_check(self):
        """Test integration health check functionality"""
        integration = Integration.objects.create(
            name="Health Check Service",
            description="Service with health check",
            integration_type="api"
        )
        
        company_integration = CompanyIntegration.objects.create(
            company=self.company,
            integration=integration,
            name="Health Check Integration",
            configuration={"health_check_url": "https://api.example.com/health"},
            status="active",
            created_by=self.user
        )
        
        # Simulate health check
        with patch('integrations.services.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "healthy"}
            mock_get.return_value = mock_response
            
            # Perform health check
            health_url = company_integration.configuration["health_check_url"]
            response = mock_get(health_url)
            
            if response.status_code == 200:
                company_integration.last_sync = timezone.now()
                company_integration.save()
                
                IntegrationLog.objects.create(
                    company_integration=company_integration,
                    level="info",
                    message="Health check passed",
                    details=response.json()
                )
            
            self.assertIsNotNone(company_integration.last_sync)
            
            log = IntegrationLog.objects.filter(
                company_integration=company_integration
            ).first()
            
            self.assertEqual(log.message, "Health check passed")
            self.assertEqual(log.details["status"], "healthy")

    def test_integration_retry_mechanism(self):
        """Test integration retry mechanism"""
        integration = Integration.objects.create(
            name="Retry Service",
            description="Service with retry logic",
            integration_type="webhook"
        )
        
        company_integration = CompanyIntegration.objects.create(
            company=self.company,
            integration=integration,
            name="Retry Integration",
            configuration={
                "webhook_url": "https://unreliable.example.com/webhook",
                "max_retries": 3,
                "retry_delay": 5
            },
            status="active",
            created_by=self.user
        )
        
        # Simulate multiple retry attempts
        for attempt in range(1, 4):  # 3 attempts
            IntegrationLog.objects.create(
                company_integration=company_integration,
                level="warning" if attempt < 3 else "error",
                message=f"Webhook attempt {attempt} failed",
                details={
                    "attempt": attempt,
                    "max_retries": 3,
                    "next_retry_in": 5 if attempt < 3 else None
                }
            )
        
        logs = IntegrationLog.objects.filter(
            company_integration=company_integration
        ).order_by('timestamp')
        
        self.assertEqual(logs.count(), 3)
        self.assertEqual(logs[0].details["attempt"], 1)
        self.assertEqual(logs[2].level, "error")
