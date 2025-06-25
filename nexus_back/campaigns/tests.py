"""
Comprehensive unit tests for campaigns functionality
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

from .models import Campaign, CampaignRecipient
from companies.models import Company
from messaging.models import Conversation

User = get_user_model()


class CampaignModelTest(TestCase):
    """Test Campaign model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="campaign_manager",
            email="manager@example.com",
            company=self.company
        )

    def test_create_campaign(self):
        """Test creating a campaign"""
        campaign = Campaign.objects.create(
            company=self.company,
            name="Summer Sale Campaign",
            description="Promote summer sale to existing customers",
            platform="whatsapp",
            message_template="Hi {{name}}! Don't miss our summer sale - get {{discount}}% off until {{end_date}}!",
            target_audience={
                "customer_type": "existing",
                "purchase_history": "has_purchased",
                "location": ["US", "CA"]
            },
            schedule_type="scheduled",
            scheduled_at=timezone.now() + timedelta(days=1),
            created_by=self.user
        )
        
        self.assertEqual(campaign.company, self.company)
        self.assertEqual(campaign.name, "Summer Sale Campaign")
        self.assertEqual(campaign.platform, "whatsapp")
        self.assertEqual(campaign.status, "draft")
        self.assertEqual(campaign.schedule_type, "scheduled")
        self.assertEqual(campaign.created_by, self.user)

    def test_campaign_str_representation(self):
        """Test campaign string representation"""
        campaign = Campaign.objects.create(
            company=self.company,
            name="Test Campaign",
            platform="telegram",
            message_template="Test message",
            created_by=self.user
        )
        
        expected_str = f"{self.company.name} - Test Campaign"
        self.assertEqual(str(campaign), expected_str)

    def test_campaign_status_transitions(self):
        """Test campaign status transitions"""
        campaign = Campaign.objects.create(
            company=self.company,
            name="Status Test Campaign",
            platform="whatsapp",
            message_template="Test message",
            created_by=self.user
        )
        
        # Initial status
        self.assertEqual(campaign.status, "draft")
        
        # Schedule campaign
        campaign.status = "scheduled"
        campaign.scheduled_at = timezone.now() + timedelta(hours=2)
        campaign.save()
        
        self.assertEqual(campaign.status, "scheduled")
        self.assertIsNotNone(campaign.scheduled_at)
        
        # Start campaign
        campaign.status = "running"
        campaign.save()
        
        self.assertEqual(campaign.status, "running")
        
        # Complete campaign
        campaign.status = "completed"
        campaign.save()
        
        self.assertEqual(campaign.status, "completed")

    def test_immediate_campaign(self):
        """Test immediate campaign creation"""
        campaign = Campaign.objects.create(
            company=self.company,
            name="Immediate Campaign",
            platform="telegram",
            message_template="Urgent announcement: {{message}}",
            schedule_type="immediate",
            created_by=self.user
        )
        
        self.assertEqual(campaign.schedule_type, "immediate")
        self.assertIsNone(campaign.scheduled_at)

    def test_recurring_campaign(self):
        """Test recurring campaign setup"""
        campaign = Campaign.objects.create(
            company=self.company,
            name="Weekly Newsletter",
            platform="whatsapp",
            message_template="This week's updates: {{content}}",
            schedule_type="recurring",
            target_audience={
                "subscription_type": "newsletter",
                "frequency": "weekly",
                "day_of_week": "monday",
                "time": "09:00"
            },
            created_by=self.user
        )
        
        self.assertEqual(campaign.schedule_type, "recurring")
        self.assertIn("frequency", campaign.target_audience)

    def test_target_audience_filtering(self):
        """Test target audience filtering criteria"""
        complex_audience = {
            "demographics": {
                "age_range": {"min": 25, "max": 45},
                "location": ["New York", "California", "Texas"]
            },
            "behavior": {
                "last_purchase_days": 30,
                "total_purchases": {"min": 2},
                "preferred_platform": ["whatsapp", "telegram"]
            },
            "engagement": {
                "opened_last_campaign": True,
                "response_rate": {"min": 0.1}
            }
        }
        
        campaign = Campaign.objects.create(
            company=self.company,
            name="Targeted Campaign",
            platform="whatsapp",
            message_template="Personalized message for {{name}}",
            target_audience=complex_audience,
            created_by=self.user
        )
        
        self.assertIn("demographics", campaign.target_audience)
        self.assertIn("behavior", campaign.target_audience)
        self.assertIn("engagement", campaign.target_audience)

    def test_platform_specific_campaigns(self):
        """Test campaigns for different platforms"""
        platforms = ["whatsapp", "telegram", "instagram", "sms"]
        
        for platform in platforms:
            campaign = Campaign.objects.create(
                company=self.company,
                name=f"{platform.title()} Campaign",
                platform=platform,
                message_template=f"Message for {platform}: {{content}}",
                created_by=self.user
            )
            
            self.assertEqual(campaign.platform, platform)


class CampaignRecipientModelTest(TestCase):
    """Test CampaignRecipient model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="campaign_manager",
            email="manager@example.com",
            company=self.company
        )
        self.campaign = Campaign.objects.create(
            company=self.company,
            name="Test Campaign",
            platform="whatsapp",
            message_template="Hello {{name}}, this is a test message!",
            created_by=self.user
        )

    def test_create_campaign_recipient(self):
        """Test creating a campaign recipient"""
        recipient = CampaignRecipient.objects.create(
            campaign=self.campaign,
            recipient_id="+1234567890",
            recipient_data={
                "name": "John Doe",
                "email": "john@example.com",
                "customer_id": "cust_123"
            },
            metadata={
                "source": "customer_database",
                "segment": "high_value"
            }
        )
        
        self.assertEqual(recipient.campaign, self.campaign)
        self.assertEqual(recipient.recipient_id, "+1234567890")
        self.assertEqual(recipient.status, "pending")
        self.assertEqual(recipient.recipient_data["name"], "John Doe")

    def test_campaign_recipient_str_representation(self):
        """Test campaign recipient string representation"""
        recipient = CampaignRecipient.objects.create(
            campaign=self.campaign,
            recipient_id="user_123",
            recipient_data={"name": "Jane Doe"}
        )
        
        expected_str = f"{self.campaign.name} - user_123"
        self.assertEqual(str(recipient), expected_str)

    def test_recipient_status_tracking(self):
        """Test recipient status tracking through campaign lifecycle"""
        recipient = CampaignRecipient.objects.create(
            campaign=self.campaign,
            recipient_id="+1234567890",
            recipient_data={"name": "John Doe"}
        )
        
        # Initial status
        self.assertEqual(recipient.status, "pending")
        
        # Mark as sent
        recipient.status = "sent"
        recipient.sent_at = timezone.now()
        recipient.save()
        
        self.assertEqual(recipient.status, "sent")
        self.assertIsNotNone(recipient.sent_at)
        
        # Mark as delivered
        recipient.status = "delivered"
        recipient.delivered_at = timezone.now()
        recipient.save()
        
        self.assertEqual(recipient.status, "delivered")
        self.assertIsNotNone(recipient.delivered_at)
        
        # Mark as opened
        recipient.status = "opened"
        recipient.metadata["opened_at"] = timezone.now().isoformat()
        recipient.save()
        
        self.assertEqual(recipient.status, "opened")

    def test_failed_recipient(self):
        """Test failed recipient handling"""
        recipient = CampaignRecipient.objects.create(
            campaign=self.campaign,
            recipient_id="invalid_number",
            recipient_data={"name": "Invalid User"},
            status="failed",
            error_message="Invalid phone number format"
        )
        
        self.assertEqual(recipient.status, "failed")
        self.assertIn("Invalid phone number", recipient.error_message)

    def test_unique_constraint(self):
        """Test unique constraint on campaign and recipient_id"""
        CampaignRecipient.objects.create(
            campaign=self.campaign,
            recipient_id="+1234567890",
            recipient_data={"name": "John Doe"}
        )
        
        # Creating another recipient with same campaign and recipient_id should fail
        with self.assertRaises(Exception):
            CampaignRecipient.objects.create(
                campaign=self.campaign,
                recipient_id="+1234567890",
                recipient_data={"name": "Jane Doe"}
            )

    def test_bulk_recipient_creation(self):
        """Test bulk recipient creation"""
        recipients_data = [
            {
                "recipient_id": "+1234567890",
                "recipient_data": {"name": "John Doe", "segment": "premium"}
            },
            {
                "recipient_id": "+1234567891", 
                "recipient_data": {"name": "Jane Smith", "segment": "standard"}
            },
            {
                "recipient_id": "+1234567892",
                "recipient_data": {"name": "Bob Johnson", "segment": "premium"}
            }
        ]
        
        recipients = []
        for data in recipients_data:
            recipient = CampaignRecipient.objects.create(
                campaign=self.campaign,
                **data
            )
            recipients.append(recipient)
        
        self.assertEqual(len(recipients), 3)
        self.assertEqual(CampaignRecipient.objects.filter(campaign=self.campaign).count(), 3)

    def test_recipient_personalization_data(self):
        """Test recipient personalization data storage"""
        personalization_data = {
            "name": "Alice Johnson",
            "email": "alice@example.com",
            "last_purchase": "2024-01-15",
            "favorite_category": "electronics",
            "discount_percentage": 15,
            "loyalty_points": 2500,
            "purchase_history": [
                {"product": "Laptop", "date": "2024-01-15", "amount": 999.99},
                {"product": "Mouse", "date": "2023-12-10", "amount": 29.99}
            ]
        }
        
        recipient = CampaignRecipient.objects.create(
            campaign=self.campaign,
            recipient_id="alice@example.com",
            recipient_data=personalization_data
        )
        
        self.assertEqual(recipient.recipient_data["name"], "Alice Johnson")
        self.assertEqual(recipient.recipient_data["discount_percentage"], 15)
        self.assertEqual(len(recipient.recipient_data["purchase_history"]), 2)


class CampaignServiceTest(TestCase):
    """Test campaign service functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="campaign_manager",
            email="manager@example.com",
            company=self.company
        )

    def test_message_template_personalization(self):
        """Test message template personalization"""
        campaign = Campaign.objects.create(
            company=self.company,
            name="Personalized Campaign",
            platform="whatsapp",
            message_template="Hi {{name}}! Your {{product}} order #{{order_id}} is ready. Total: ${{total}}. Pick up by {{pickup_date}}.",
            created_by=self.user
        )
        
        recipient = CampaignRecipient.objects.create(
            campaign=campaign,
            recipient_id="+1234567890",
            recipient_data={
                "name": "John Doe",
                "product": "Wireless Headphones",
                "order_id": "ORD-12345",
                "total": "199.99",
                "pickup_date": "March 15th"
            }
        )
        
        # Simulate message personalization
        template = campaign.message_template
        personalized_message = template
        
        for key, value in recipient.recipient_data.items():
            personalized_message = personalized_message.replace(f"{{{{{key}}}}}", str(value))
        
        expected_message = "Hi John Doe! Your Wireless Headphones order #ORD-12345 is ready. Total: $199.99. Pick up by March 15th."
        self.assertEqual(personalized_message, expected_message)

    def test_audience_targeting_logic(self):
        """Test audience targeting logic"""
        # Create conversations to simulate customer data
        customers = [
            {"phone": "+1111111111", "name": "Premium Customer", "purchases": 5, "last_purchase": 10},
            {"phone": "+2222222222", "name": "Regular Customer", "purchases": 2, "last_purchase": 45},
            {"phone": "+3333333333", "name": "New Customer", "purchases": 1, "last_purchase": 5},
            {"phone": "+4444444444", "name": "Inactive Customer", "purchases": 3, "last_purchase": 90}
        ]
        
        for customer in customers:
            conversation = Conversation.objects.create(
                company=self.company,
                external_id=customer["phone"],
                platform="whatsapp",
                metadata={
                    "customer_name": customer["name"],
                    "purchase_count": customer["purchases"],
                    "days_since_last_purchase": customer["last_purchase"]
                }
            )
        
        campaign = Campaign.objects.create(
            company=self.company,
            name="Win-back Campaign",
            platform="whatsapp",
            message_template="Hi {{name}}, we miss you! Come back for a special {{discount}}% discount.",
            target_audience={
                "purchase_count": {"min": 2},
                "days_since_last_purchase": {"min": 30, "max": 60}
            },
            created_by=self.user
        )
        
        # Apply targeting logic
        target_criteria = campaign.target_audience
        eligible_conversations = Conversation.objects.filter(
            company=self.company,
            platform=campaign.platform
        )
        
        # Filter based on criteria
        if "purchase_count" in target_criteria:
            min_purchases = target_criteria["purchase_count"].get("min", 0)
            eligible_conversations = eligible_conversations.filter(
                metadata__purchase_count__gte=min_purchases
            )
        
        if "days_since_last_purchase" in target_criteria:
            days_criteria = target_criteria["days_since_last_purchase"]
            min_days = days_criteria.get("min", 0)
            max_days = days_criteria.get("max", 9999)
            
            eligible_conversations = eligible_conversations.filter(
                metadata__days_since_last_purchase__gte=min_days,
                metadata__days_since_last_purchase__lte=max_days
            )
        
        # Should only match "Regular Customer" (2 purchases, 45 days)
        self.assertEqual(eligible_conversations.count(), 1)
        eligible_customer = eligible_conversations.first()
        self.assertEqual(eligible_customer.metadata["customer_name"], "Regular Customer")

    @patch('campaigns.services.send_message')
    def test_campaign_execution(self, mock_send_message):
        """Test campaign execution and message sending"""
        mock_send_message.return_value = {"status": "sent", "message_id": "msg_123"}
        
        campaign = Campaign.objects.create(
            company=self.company,
            name="Flash Sale Campaign",
            platform="whatsapp",
            message_template="Flash Sale! Get {{discount}}% off everything. Code: {{code}}",
            status="running",
            created_by=self.user
        )
        
        # Add recipients
        recipients_data = [
            {"recipient_id": "+1111111111", "recipient_data": {"name": "John", "discount": 20, "code": "FLASH20"}},
            {"recipient_id": "+2222222222", "recipient_data": {"name": "Jane", "discount": 15, "code": "FLASH15"}},
            {"recipient_id": "+3333333333", "recipient_data": {"name": "Bob", "discount": 25, "code": "FLASH25"}}
        ]
        
        for data in recipients_data:
            CampaignRecipient.objects.create(campaign=campaign, **data)
        
        # Execute campaign
        recipients = CampaignRecipient.objects.filter(campaign=campaign, status="pending")
        
        for recipient in recipients:
            # Personalize message
            message = campaign.message_template
            for key, value in recipient.recipient_data.items():
                message = message.replace(f"{{{{{key}}}}}", str(value))
            
            # Send message
            result = mock_send_message(
                platform=campaign.platform,
                recipient_id=recipient.recipient_id,
                message=message
            )
            
            # Update recipient status
            if result["status"] == "sent":
                recipient.status = "sent"
                recipient.sent_at = timezone.now()
                recipient.metadata["message_id"] = result["message_id"]
                recipient.save()
        
        # Verify all recipients were processed
        sent_recipients = CampaignRecipient.objects.filter(campaign=campaign, status="sent")
        self.assertEqual(sent_recipients.count(), 3)
        self.assertEqual(mock_send_message.call_count, 3)

    def test_campaign_scheduling(self):
        """Test campaign scheduling functionality"""
        future_time = timezone.now() + timedelta(hours=24)
        
        campaign = Campaign.objects.create(
            company=self.company,
            name="Scheduled Campaign",
            platform="telegram",
            message_template="Tomorrow's special offer: {{offer}}",
            schedule_type="scheduled",
            scheduled_at=future_time,
            status="scheduled",
            created_by=self.user
        )
        
        # Check if campaign should run now
        current_time = timezone.now()
        should_run = (
            campaign.status == "scheduled" and
            campaign.scheduled_at and
            campaign.scheduled_at <= current_time
        )
        
        self.assertFalse(should_run)  # Should not run yet
        
        # Simulate time passing
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = future_time + timedelta(minutes=1)
            
            current_time = mock_now()
            should_run = (
                campaign.status == "scheduled" and
                campaign.scheduled_at and
                campaign.scheduled_at <= current_time
            )
            
            self.assertTrue(should_run)  # Should run now

    def test_campaign_performance_tracking(self):
        """Test campaign performance tracking"""
        campaign = Campaign.objects.create(
            company=self.company,
            name="Performance Tracking Campaign",
            platform="whatsapp",
            message_template="Check out our new product: {{product_url}}",
            status="completed",
            created_by=self.user
        )
        
        # Create recipients with various statuses
        recipient_statuses = [
            ("sent", 5),
            ("delivered", 4),
            ("opened", 3),
            ("clicked", 2),
            ("failed", 1)
        ]
        
        total_recipients = 0
        for status, count in recipient_statuses:
            for i in range(count):
                total_recipients += 1
                CampaignRecipient.objects.create(
                    campaign=campaign,
                    recipient_id=f"+111111111{total_recipients}",
                    recipient_data={"name": f"User {total_recipients}"},
                    status=status
                )
        
        # Calculate performance metrics
        recipients = CampaignRecipient.objects.filter(campaign=campaign)
        
        total_sent = recipients.filter(status__in=["sent", "delivered", "opened", "clicked"]).count()
        total_delivered = recipients.filter(status__in=["delivered", "opened", "clicked"]).count()
        total_opened = recipients.filter(status__in=["opened", "clicked"]).count()
        total_clicked = recipients.filter(status="clicked").count()
        total_failed = recipients.filter(status="failed").count()
        
        delivery_rate = (total_delivered / total_recipients) * 100 if total_recipients > 0 else 0
        open_rate = (total_opened / total_delivered) * 100 if total_delivered > 0 else 0
        click_rate = (total_clicked / total_opened) * 100 if total_opened > 0 else 0
        
        self.assertEqual(total_recipients, 15)
        self.assertEqual(total_sent, 14)  # All except failed
        self.assertEqual(total_delivered, 9)  # delivered + opened + clicked
        self.assertEqual(total_opened, 5)  # opened + clicked
        self.assertEqual(total_clicked, 2)
        self.assertEqual(total_failed, 1)
        
        self.assertAlmostEqual(delivery_rate, 60.0, places=1)  # 9/15 * 100
        self.assertAlmostEqual(open_rate, 55.6, places=1)  # 5/9 * 100
        self.assertAlmostEqual(click_rate, 40.0, places=1)  # 2/5 * 100

    def test_campaign_pause_and_resume(self):
        """Test campaign pause and resume functionality"""
        campaign = Campaign.objects.create(
            company=self.company,
            name="Pauseable Campaign",
            platform="whatsapp",
            message_template="Test message",
            status="running",
            created_by=self.user
        )
        
        # Add recipients
        for i in range(5):
            CampaignRecipient.objects.create(
                campaign=campaign,
                recipient_id=f"+111111111{i}",
                recipient_data={"name": f"User {i}"}
            )
        
        # Pause campaign
        campaign.status = "paused"
        campaign.save()
        
        # Check that no new messages should be sent
        pending_recipients = CampaignRecipient.objects.filter(
            campaign=campaign,
            status="pending"
        )
        
        should_send = campaign.status == "running"
        self.assertFalse(should_send)
        self.assertEqual(pending_recipients.count(), 5)
        
        # Resume campaign
        campaign.status = "running"
        campaign.save()
        
        should_send = campaign.status == "running"
        self.assertTrue(should_send)

    def test_a_b_testing_campaigns(self):
        """Test A/B testing campaign setup"""
        # Campaign A
        campaign_a = Campaign.objects.create(
            company=self.company,
            name="A/B Test - Version A",
            platform="whatsapp",
            message_template="Get {{discount}}% off! Limited time offer.",
            target_audience={"ab_test_group": "A"},
            created_by=self.user
        )
        
        # Campaign B
        campaign_b = Campaign.objects.create(
            company=self.company,
            name="A/B Test - Version B",
            platform="whatsapp",
            message_template="Save big with {{discount}}% discount! Act now!",
            target_audience={"ab_test_group": "B"},
            created_by=self.user
        )
        
        # Distribute recipients between A and B groups
        all_recipients = [f"+111111111{i}" for i in range(100)]
        
        for i, recipient_id in enumerate(all_recipients):
            # Split 50/50
            campaign = campaign_a if i % 2 == 0 else campaign_b
            group = "A" if i % 2 == 0 else "B"
            
            CampaignRecipient.objects.create(
                campaign=campaign,
                recipient_id=recipient_id,
                recipient_data={
                    "name": f"User {i}",
                    "discount": 20,
                    "ab_test_group": group
                }
            )
        
        # Verify split
        group_a_count = CampaignRecipient.objects.filter(campaign=campaign_a).count()
        group_b_count = CampaignRecipient.objects.filter(campaign=campaign_b).count()
        
        self.assertEqual(group_a_count, 50)
        self.assertEqual(group_b_count, 50)
