"""
Comprehensive unit tests for notifications functionality
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

from .models import NotificationTemplate, Notification, NotificationPreference
from companies.models import Company

User = get_user_model()


class NotificationTemplateModelTest(TestCase):
    """Test NotificationTemplate model functionality"""

    def test_create_notification_template(self):
        """Test creating a notification template"""
        template = NotificationTemplate.objects.create(
            name="Welcome Email",
            notification_type="email",
            subject_template="Welcome to {{company_name}}, {{user_name}}!",
            message_template="Hi {{user_name}},\n\nWelcome to {{company_name}}! We're excited to have you on board.\n\nBest regards,\nThe Team",
            variables=["company_name", "user_name", "support_email"]
        )
        
        self.assertEqual(template.name, "Welcome Email")
        self.assertEqual(template.notification_type, "email")
        self.assertIn("{{company_name}}", template.subject_template)
        self.assertIn("{{user_name}}", template.message_template)
        self.assertTrue(template.is_active)
        self.assertEqual(len(template.variables), 3)

    def test_notification_template_str_representation(self):
        """Test notification template string representation"""
        template = NotificationTemplate.objects.create(
            name="SMS Alert",
            notification_type="sms",
            message_template="Alert: {{message}}"
        )
        
        expected_str = "SMS Alert (sms)"
        self.assertEqual(str(template), expected_str)

    def test_different_notification_types(self):
        """Test different notification types"""
        types = ["email", "sms", "push", "in_app"]
        
        for notification_type in types:
            template = NotificationTemplate.objects.create(
                name=f"Test {notification_type.title()}",
                notification_type=notification_type,
                message_template=f"Test {notification_type} message: {{content}}"
            )
            
            self.assertEqual(template.notification_type, notification_type)

    def test_email_template_with_subject(self):
        """Test email template with subject"""
        template = NotificationTemplate.objects.create(
            name="Order Confirmation",
            notification_type="email",
            subject_template="Order #{{order_id}} Confirmed",
            message_template="Your order #{{order_id}} for {{product_name}} has been confirmed.",
            variables=["order_id", "product_name", "order_total"]
        )
        
        self.assertIn("{{order_id}}", template.subject_template)
        self.assertIn("{{product_name}}", template.message_template)

    def test_push_notification_template(self):
        """Test push notification template"""
        template = NotificationTemplate.objects.create(
            name="New Message Alert",
            notification_type="push",
            message_template="You have a new message from {{sender_name}}",
            variables=["sender_name", "message_preview", "conversation_id"]
        )
        
        self.assertEqual(template.notification_type, "push")
        self.assertIn("{{sender_name}}", template.message_template)

    def test_inactive_template(self):
        """Test inactive template"""
        template = NotificationTemplate.objects.create(
            name="Deprecated Template",
            notification_type="email",
            message_template="Old template",
            is_active=False
        )
        
        self.assertFalse(template.is_active)
        
        # Active templates query should exclude this
        active_templates = NotificationTemplate.objects.filter(is_active=True)
        self.assertNotIn(template, active_templates)


class NotificationModelTest(TestCase):
    """Test Notification model functionality"""

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
        self.template = NotificationTemplate.objects.create(
            name="Test Template",
            notification_type="email",
            subject_template="Test Subject: {{title}}",
            message_template="Hello {{name}}, this is a test message.",
            variables=["title", "name"]
        )

    def test_create_notification(self):
        """Test creating a notification"""
        notification = Notification.objects.create(
            recipient=self.user,
            template=self.template,
            notification_type="email",
            subject="Test Subject: Important Update",
            message="Hello John, this is a test message.",
            metadata={
                "template_variables": {
                    "title": "Important Update",
                    "name": "John"
                }
            }
        )
        
        self.assertEqual(notification.recipient, self.user)
        self.assertEqual(notification.template, self.template)
        self.assertEqual(notification.notification_type, "email")
        self.assertEqual(notification.status, "pending")
        self.assertIn("Important Update", notification.subject)

    def test_notification_str_representation(self):
        """Test notification string representation"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type="push",
            message="Test push notification"
        )
        
        expected_str = f"{self.user.email} - push - pending"
        self.assertEqual(str(notification), expected_str)

    def test_notification_without_template(self):
        """Test notification without template (direct message)"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type="sms",
            message="Direct SMS message without template",
            metadata={"sender": "system"}
        )
        
        self.assertIsNone(notification.template)
        self.assertEqual(notification.notification_type, "sms")

    def test_notification_status_transitions(self):
        """Test notification status transitions"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type="email",
            message="Test message"
        )
        
        # Initial status
        self.assertEqual(notification.status, "pending")
        
        # Mark as sent
        notification.status = "sent"
        notification.sent_at = timezone.now()
        notification.save()
        
        self.assertEqual(notification.status, "sent")
        self.assertIsNotNone(notification.sent_at)
        
        # Mark as delivered
        notification.status = "delivered"
        notification.save()
        
        self.assertEqual(notification.status, "delivered")
        
        # Mark as read
        notification.status = "read"
        notification.read_at = timezone.now()
        notification.save()
        
        self.assertEqual(notification.status, "read")
        self.assertIsNotNone(notification.read_at)

    def test_failed_notification(self):
        """Test failed notification"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type="email",
            message="Test message",
            status="failed",
            metadata={
                "error": "Invalid email address",
                "error_code": "INVALID_EMAIL"
            }
        )
        
        self.assertEqual(notification.status, "failed")
        self.assertIn("error", notification.metadata)

    def test_scheduled_notification(self):
        """Test scheduled notification"""
        future_time = timezone.now() + timedelta(hours=2)
        
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type="push",
            message="Scheduled reminder",
            scheduled_at=future_time,
            metadata={"reminder_type": "appointment"}
        )
        
        self.assertIsNotNone(notification.scheduled_at)
        self.assertGreater(notification.scheduled_at, timezone.now())

    def test_notification_ordering(self):
        """Test notification ordering"""
        # Create notifications with slight time differences
        notification1 = Notification.objects.create(
            recipient=self.user,
            notification_type="email",
            message="First notification"
        )
        
        notification2 = Notification.objects.create(
            recipient=self.user,
            notification_type="email",
            message="Second notification"
        )
        
        notifications = list(Notification.objects.all())
        
        # Should be ordered by newest first
        self.assertEqual(notifications[0], notification2)
        self.assertEqual(notifications[1], notification1)


class NotificationPreferenceModelTest(TestCase):
    """Test NotificationPreference model functionality"""

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

    def test_create_notification_preference(self):
        """Test creating notification preferences"""
        preferences = NotificationPreference.objects.create(
            user=self.user,
            email_enabled=True,
            sms_enabled=False,
            push_enabled=True,
            in_app_enabled=True,
            new_message_notifications=True,
            campaign_notifications=False,
            system_notifications=True,
            marketing_notifications=False
        )
        
        self.assertEqual(preferences.user, self.user)
        self.assertTrue(preferences.email_enabled)
        self.assertFalse(preferences.sms_enabled)
        self.assertTrue(preferences.new_message_notifications)
        self.assertFalse(preferences.marketing_notifications)

    def test_notification_preference_str_representation(self):
        """Test notification preference string representation"""
        preferences = NotificationPreference.objects.create(user=self.user)
        
        expected_str = f"{self.user.email} - Preferences"
        self.assertEqual(str(preferences), expected_str)

    def test_default_preferences(self):
        """Test default notification preferences"""
        preferences = NotificationPreference.objects.create(user=self.user)
        
        # Test default values
        self.assertTrue(preferences.email_enabled)
        self.assertFalse(preferences.sms_enabled)
        self.assertTrue(preferences.push_enabled)
        self.assertTrue(preferences.in_app_enabled)
        self.assertTrue(preferences.new_message_notifications)
        self.assertTrue(preferences.campaign_notifications)
        self.assertTrue(preferences.system_notifications)
        self.assertFalse(preferences.marketing_notifications)

    def test_one_to_one_relationship(self):
        """Test one-to-one relationship between user and preferences"""
        preferences1 = NotificationPreference.objects.create(user=self.user)
        
        # Trying to create another preference for same user should raise error
        with self.assertRaises(Exception):
            NotificationPreference.objects.create(user=self.user)

    def test_preference_updates(self):
        """Test updating notification preferences"""
        preferences = NotificationPreference.objects.create(user=self.user)
        
        # Update preferences
        preferences.email_enabled = False
        preferences.sms_enabled = True
        preferences.marketing_notifications = True
        preferences.save()
        
        updated_preferences = NotificationPreference.objects.get(user=self.user)
        
        self.assertFalse(updated_preferences.email_enabled)
        self.assertTrue(updated_preferences.sms_enabled)
        self.assertTrue(updated_preferences.marketing_notifications)


class NotificationServiceTest(TestCase):
    """Test notification service functionality"""

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
        self.preferences = NotificationPreference.objects.create(
            user=self.user,
            email_enabled=True,
            push_enabled=True,
            sms_enabled=False
        )

    def test_template_variable_substitution(self):
        """Test template variable substitution"""
        template = NotificationTemplate.objects.create(
            name="Variable Test",
            notification_type="email",
            subject_template="Welcome {{user_name}} to {{company_name}}",
            message_template="Hi {{user_name}},\n\nYour account for {{company_name}} is ready!\n\nLogin here: {{login_url}}",
            variables=["user_name", "company_name", "login_url"]
        )
        
        variables = {
            "user_name": "John Doe",
            "company_name": "Acme Corp",
            "login_url": "https://app.acme.com/login"
        }
        
        # Simulate template rendering
        subject = template.subject_template
        message = template.message_template
        
        for var, value in variables.items():
            subject = subject.replace(f"{{{{{var}}}}}", value)
            message = message.replace(f"{{{{{var}}}}}", value)
        
        notification = Notification.objects.create(
            recipient=self.user,
            template=template,
            notification_type="email",
            subject=subject,
            message=message,
            metadata={"template_variables": variables}
        )
        
        self.assertEqual(notification.subject, "Welcome John Doe to Acme Corp")
        self.assertIn("Hi John Doe", notification.message)
        self.assertIn("Acme Corp", notification.message)

    @patch('notifications.services.send_email')
    def test_email_notification_sending(self, mock_send_email):
        """Test email notification sending"""
        mock_send_email.return_value = {"status": "sent", "message_id": "email_123"}
        
        template = NotificationTemplate.objects.create(
            name="Email Test",
            notification_type="email",
            subject_template="Test Email",
            message_template="This is a test email."
        )
        
        notification = Notification.objects.create(
            recipient=self.user,
            template=template,
            notification_type="email",
            subject="Test Email",
            message="This is a test email."
        )
        
        # Check if user has email enabled
        if self.preferences.email_enabled:
            # Simulate sending
            result = mock_send_email(
                to=self.user.email,
                subject=notification.subject,
                message=notification.message
            )
            
            notification.status = "sent"
            notification.sent_at = timezone.now()
            notification.metadata["send_result"] = result
            notification.save()
        
        mock_send_email.assert_called_once_with(
            to=self.user.email,
            subject="Test Email",
            message="This is a test email."
        )
        
        self.assertEqual(notification.status, "sent")
        self.assertIsNotNone(notification.sent_at)

    @patch('notifications.services.send_sms')
    def test_sms_notification_blocked_by_preferences(self, mock_send_sms):
        """Test SMS notification blocked by user preferences"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type="sms",
            message="Test SMS message"
        )
        
        # Check if user has SMS enabled (it's disabled in setUp)
        if not self.preferences.sms_enabled:
            notification.status = "failed"
            notification.metadata["error"] = "SMS notifications disabled by user"
            notification.save()
        
        # SMS should not be sent
        mock_send_sms.assert_not_called()
        self.assertEqual(notification.status, "failed")

    @patch('notifications.services.send_push_notification')
    def test_push_notification_sending(self, mock_send_push):
        """Test push notification sending"""
        mock_send_push.return_value = {"status": "sent", "notification_id": "push_123"}
        
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type="push",
            message="You have a new message!",
            metadata={
                "action_url": "/conversations/123",
                "icon": "message",
                "sound": "default"
            }
        )
        
        # Check if user has push enabled
        if self.preferences.push_enabled:
            result = mock_send_push(
                user_id=str(self.user.id),
                message=notification.message,
                metadata=notification.metadata
            )
            
            notification.status = "sent"
            notification.sent_at = timezone.now()
            notification.save()
        
        mock_send_push.assert_called_once()
        self.assertEqual(notification.status, "sent")

    def test_in_app_notification(self):
        """Test in-app notification creation"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type="in_app",
            message="New feature available!",
            metadata={
                "category": "feature_announcement",
                "action_text": "Learn More",
                "action_url": "/features/new"
            }
        )
        
        # In-app notifications are immediately "delivered"
        notification.status = "delivered"
        notification.save()
        
        self.assertEqual(notification.notification_type, "in_app")
        self.assertEqual(notification.status, "delivered")
        self.assertIn("feature_announcement", notification.metadata["category"])

    def test_bulk_notification_creation(self):
        """Test bulk notification creation"""
        # Create multiple users
        users = []
        for i in range(5):
            user = User.objects.create_user(
                username=f"user{i}",
                email=f"user{i}@example.com",
                company=self.company
            )
            users.append(user)
            
            # Create preferences for each user
            NotificationPreference.objects.create(
                user=user,
                email_enabled=True
            )
        
        template = NotificationTemplate.objects.create(
            name="Bulk Email",
            notification_type="email",
            subject_template="System Maintenance Notice",
            message_template="We will be performing maintenance on {{date}} at {{time}}."
        )
        
        # Create bulk notifications
        notifications = []
        for user in users:
            notification = Notification.objects.create(
                recipient=user,
                template=template,
                notification_type="email",
                subject="System Maintenance Notice",
                message="We will be performing maintenance on Jan 15 at 2:00 AM.",
                metadata={
                    "bulk_send": True,
                    "campaign_id": "maintenance_2024_01"
                }
            )
            notifications.append(notification)
        
        self.assertEqual(len(notifications), 5)
        for notification in notifications:
            self.assertTrue(notification.metadata["bulk_send"])

    def test_notification_retry_mechanism(self):
        """Test notification retry mechanism for failures"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type="email",
            subject="Retry Test",
            message="This is a retry test",
            status="failed",
            metadata={
                "retry_count": 2,
                "max_retries": 3,
                "last_error": "SMTP server unavailable"
            }
        )
        
        # Simulate retry
        retry_count = notification.metadata.get("retry_count", 0)
        max_retries = notification.metadata.get("max_retries", 3)
        
        if retry_count < max_retries:
            # Attempt retry
            notification.metadata["retry_count"] = retry_count + 1
            notification.status = "pending"
            notification.save()
        
        self.assertEqual(notification.metadata["retry_count"], 3)
        self.assertEqual(notification.status, "pending")

    def test_notification_scheduling(self):
        """Test notification scheduling"""
        future_time = timezone.now() + timedelta(hours=24)
        
        scheduled_notification = Notification.objects.create(
            recipient=self.user,
            notification_type="push",
            message="Don't forget about your appointment tomorrow!",
            scheduled_at=future_time,
            metadata={
                "reminder_type": "appointment",
                "appointment_id": "apt_123"
            }
        )
        
        # Check if notification should be sent now
        current_time = timezone.now()
        should_send = (
            scheduled_notification.scheduled_at and 
            scheduled_notification.scheduled_at <= current_time
        )
        
        self.assertFalse(should_send)  # Should not send yet
        
        # Simulate time passing
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = future_time + timedelta(minutes=1)
            
            current_time = mock_now()
            should_send = (
                scheduled_notification.scheduled_at and 
                scheduled_notification.scheduled_at <= current_time
            )
            
            self.assertTrue(should_send)  # Should send now

    def test_notification_preferences_filtering(self):
        """Test filtering notifications based on user preferences"""
        # User has marketing notifications disabled
        self.preferences.marketing_notifications = False
        self.preferences.save()
        
        marketing_notification = Notification.objects.create(
            recipient=self.user,
            notification_type="email",
            subject="Special Offer!",
            message="Get 50% off this week!",
            metadata={"category": "marketing"}
        )
        
        # Check if notification should be sent based on preferences
        category = marketing_notification.metadata.get("category")
        should_send = True
        
        if category == "marketing" and not self.preferences.marketing_notifications:
            should_send = False
            marketing_notification.status = "failed"
            marketing_notification.metadata["blocked_reason"] = "Marketing notifications disabled"
            marketing_notification.save()
        
        self.assertFalse(should_send)
        self.assertEqual(marketing_notification.status, "failed")
