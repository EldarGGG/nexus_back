"""
Comprehensive unit tests for billing functionality
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal
from unittest.mock import patch, Mock

from .models import SubscriptionPlan, Subscription, Invoice, UsageMetrics
from companies.models import Company
from messaging.models import Conversation, Message

User = get_user_model()


class SubscriptionPlanModelTest(TestCase):
    """Test SubscriptionPlan model functionality"""

    def test_create_subscription_plan(self):
        """Test creating a subscription plan"""
        plan = SubscriptionPlan.objects.create(
            name="Professional Plan",
            plan_type="professional",
            description="Perfect for growing businesses",
            price_monthly=Decimal('99.99'),
            price_yearly=Decimal('999.99'),
            max_users=25,
            max_conversations_per_month=10000,
            max_ai_requests_per_month=50000,
            features=[
                "Multi-platform messaging",
                "AI responses",
                "Analytics dashboard",
                "API access"
            ]
        )
        
        self.assertEqual(plan.name, "Professional Plan")
        self.assertEqual(plan.plan_type, "professional")
        self.assertEqual(plan.price_monthly, Decimal('99.99'))
        self.assertEqual(plan.price_yearly, Decimal('999.99'))
        self.assertEqual(plan.max_users, 25)
        self.assertTrue(plan.is_active)
        self.assertEqual(len(plan.features), 4)

    def test_subscription_plan_str_representation(self):
        """Test subscription plan string representation"""
        plan = SubscriptionPlan.objects.create(
            name="Starter Plan",
            plan_type="starter",
            description="Basic plan",
            price_monthly=Decimal('29.99'),
            price_yearly=Decimal('299.99'),
            max_users=5,
            max_conversations_per_month=1000,
            max_ai_requests_per_month=5000
        )
        
        self.assertEqual(str(plan), "Starter Plan")

    def test_plan_feature_management(self):
        """Test plan feature management"""
        plan = SubscriptionPlan.objects.create(
            name="Enterprise Plan",
            plan_type="enterprise",
            description="Full-featured plan",
            price_monthly=Decimal('299.99'),
            price_yearly=Decimal('2999.99'),
            max_users=100,
            max_conversations_per_month=100000,
            max_ai_requests_per_month=500000,
            features=[
                "Unlimited messaging",
                "Advanced AI",
                "Custom integrations",
                "Dedicated support",
                "White-label options"
            ]
        )
        
        self.assertIn("Unlimited messaging", plan.features)
        self.assertIn("White-label options", plan.features)
        self.assertEqual(len(plan.features), 5)

    def test_plan_pricing_validation(self):
        """Test plan pricing validation"""
        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            plan_type="professional",
            description="Test",
            price_monthly=Decimal('100.00'),
            price_yearly=Decimal('1000.00'),
            max_users=10,
            max_conversations_per_month=5000,
            max_ai_requests_per_month=25000
        )
        
        # Yearly should be less than 12 times monthly (discount)
        monthly_yearly = plan.price_monthly * 12
        self.assertLess(plan.price_yearly, monthly_yearly)

    def test_inactive_plan(self):
        """Test inactive plan functionality"""
        plan = SubscriptionPlan.objects.create(
            name="Deprecated Plan",
            plan_type="starter",
            description="Old plan",
            price_monthly=Decimal('19.99'),
            price_yearly=Decimal('199.99'),
            max_users=3,
            max_conversations_per_month=500,
            max_ai_requests_per_month=2500,
            is_active=False
        )
        
        self.assertFalse(plan.is_active)
        
        # Active plans query should not include this plan
        active_plans = SubscriptionPlan.objects.filter(is_active=True)
        self.assertNotIn(plan, active_plans)


class SubscriptionModelTest(TestCase):
    """Test Subscription model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Professional Plan",
            plan_type="professional",
            description="Test plan",
            price_monthly=Decimal('99.99'),
            price_yearly=Decimal('999.99'),
            max_users=25,
            max_conversations_per_month=10000,
            max_ai_requests_per_month=50000
        )

    def test_create_subscription(self):
        """Test creating a subscription"""
        start_date = timezone.now()
        end_date = start_date + timedelta(days=30)
        
        subscription = Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            started_at=start_date,
            current_period_start=start_date,
            current_period_end=end_date,
            stripe_subscription_id="sub_123456789"
        )
        
        self.assertEqual(subscription.company, self.company)
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.status, "active")
        self.assertEqual(subscription.stripe_subscription_id, "sub_123456789")
        self.assertFalse(subscription.is_trial)

    def test_subscription_str_representation(self):
        """Test subscription string representation"""
        subscription = Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            started_at=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        expected_str = f"{self.company.name} - {self.plan.name}"
        self.assertEqual(str(subscription), expected_str)

    def test_trial_subscription(self):
        """Test trial subscription"""
        start_date = timezone.now()
        trial_end = start_date + timedelta(days=14)
        
        subscription = Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            started_at=start_date,
            current_period_start=start_date,
            current_period_end=trial_end,
            is_trial=True,
            trial_ends_at=trial_end
        )
        
        self.assertTrue(subscription.is_trial)
        self.assertIsNotNone(subscription.trial_ends_at)

    def test_subscription_status_changes(self):
        """Test subscription status changes"""
        subscription = Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            started_at=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        # Test status transitions
        self.assertEqual(subscription.status, "active")
        
        subscription.status = "past_due"
        subscription.save()
        self.assertEqual(subscription.status, "past_due")
        
        subscription.status = "cancelled"
        subscription.save()
        self.assertEqual(subscription.status, "cancelled")

    def test_one_to_one_relationship(self):
        """Test one-to-one relationship between company and subscription"""
        subscription1 = Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            started_at=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        # Trying to create another subscription for same company should raise error
        with self.assertRaises(Exception):
            Subscription.objects.create(
                company=self.company,
                plan=self.plan,
                started_at=timezone.now(),
                current_period_start=timezone.now(),
                current_period_end=timezone.now() + timedelta(days=30)
            )


class InvoiceModelTest(TestCase):
    """Test Invoice model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Professional Plan",
            plan_type="professional",
            description="Test plan",
            price_monthly=Decimal('99.99'),
            price_yearly=Decimal('999.99'),
            max_users=25,
            max_conversations_per_month=10000,
            max_ai_requests_per_month=50000
        )
        self.subscription = Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            started_at=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )

    def test_create_invoice(self):
        """Test creating an invoice"""
        invoice = Invoice.objects.create(
            company=self.company,
            subscription=self.subscription,
            invoice_number="INV-2024-001",
            amount=Decimal('99.99'),
            tax_amount=Decimal('9.99'),
            total_amount=Decimal('109.98'),
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30),
            stripe_invoice_id="in_123456789"
        )
        
        self.assertEqual(invoice.company, self.company)
        self.assertEqual(invoice.subscription, self.subscription)
        self.assertEqual(invoice.invoice_number, "INV-2024-001")
        self.assertEqual(invoice.amount, Decimal('99.99'))
        self.assertEqual(invoice.tax_amount, Decimal('9.99'))
        self.assertEqual(invoice.total_amount, Decimal('109.98'))
        self.assertEqual(invoice.status, "pending")

    def test_invoice_str_representation(self):
        """Test invoice string representation"""
        invoice = Invoice.objects.create(
            company=self.company,
            subscription=self.subscription,
            invoice_number="INV-2024-002",
            amount=Decimal('99.99'),
            total_amount=Decimal('99.99'),
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        expected_str = f"INV-2024-002 - {self.company.name}"
        self.assertEqual(str(invoice), expected_str)

    def test_invoice_number_uniqueness(self):
        """Test invoice number uniqueness"""
        Invoice.objects.create(
            company=self.company,
            subscription=self.subscription,
            invoice_number="INV-2024-003",
            amount=Decimal('99.99'),
            total_amount=Decimal('99.99'),
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        # Creating another invoice with same number should raise error
        with self.assertRaises(Exception):
            Invoice.objects.create(
                company=self.company,
                subscription=self.subscription,
                invoice_number="INV-2024-003",
                amount=Decimal('199.99'),
                total_amount=Decimal('199.99'),
                period_start=timezone.now(),
                period_end=timezone.now() + timedelta(days=30)
            )

    def test_invoice_payment(self):
        """Test invoice payment status"""
        invoice = Invoice.objects.create(
            company=self.company,
            subscription=self.subscription,
            invoice_number="INV-2024-004",
            amount=Decimal('99.99'),
            total_amount=Decimal('99.99'),
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        # Initially pending
        self.assertEqual(invoice.status, "pending")
        self.assertIsNone(invoice.paid_at)
        
        # Mark as paid
        invoice.status = "paid"
        invoice.paid_at = timezone.now()
        invoice.save()
        
        self.assertEqual(invoice.status, "paid")
        self.assertIsNotNone(invoice.paid_at)

    def test_invoice_total_calculation(self):
        """Test invoice total calculation"""
        base_amount = Decimal('100.00')
        tax_amount = Decimal('10.00')
        expected_total = base_amount + tax_amount
        
        invoice = Invoice.objects.create(
            company=self.company,
            subscription=self.subscription,
            invoice_number="INV-2024-005",
            amount=base_amount,
            tax_amount=tax_amount,
            total_amount=expected_total,
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        self.assertEqual(invoice.total_amount, expected_total)

    def test_failed_invoice(self):
        """Test failed invoice handling"""
        invoice = Invoice.objects.create(
            company=self.company,
            subscription=self.subscription,
            invoice_number="INV-2024-006",
            amount=Decimal('99.99'),
            total_amount=Decimal('99.99'),
            status="failed",
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        self.assertEqual(invoice.status, "failed")


class UsageMetricsModelTest(TestCase):
    """Test UsageMetrics model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.today = date.today()

    def test_create_usage_metrics(self):
        """Test creating usage metrics"""
        metrics = UsageMetrics.objects.create(
            company=self.company,
            date=self.today,
            conversations_count=150,
            messages_count=750,
            ai_requests_count=300,
            storage_used_mb=125.5
        )
        
        self.assertEqual(metrics.company, self.company)
        self.assertEqual(metrics.date, self.today)
        self.assertEqual(metrics.conversations_count, 150)
        self.assertEqual(metrics.messages_count, 750)
        self.assertEqual(metrics.ai_requests_count, 300)
        self.assertEqual(metrics.storage_used_mb, 125.5)

    def test_usage_metrics_str_representation(self):
        """Test usage metrics string representation"""
        metrics = UsageMetrics.objects.create(
            company=self.company,
            date=self.today,
            conversations_count=100
        )
        
        expected_str = f"{self.company.name} - {self.today}"
        self.assertEqual(str(metrics), expected_str)

    def test_usage_metrics_unique_constraint(self):
        """Test unique constraint on company and date"""
        UsageMetrics.objects.create(
            company=self.company,
            date=self.today,
            conversations_count=100
        )
        
        # Creating another metric for same company and date should raise error
        with self.assertRaises(Exception):
            UsageMetrics.objects.create(
                company=self.company,
                date=self.today,
                conversations_count=200
            )

    def test_usage_tracking_integration(self):
        """Test usage tracking with actual conversation and message data"""
        # Create conversations and messages
        for i in range(5):
            conversation = Conversation.objects.create(
                company=self.company,
                external_id=f"usage_conv_{i}",
                platform="whatsapp"
            )
            
            # Create messages for each conversation
            for j in range(3):
                Message.objects.create(
                    conversation=conversation,
                    direction="incoming" if j % 2 == 0 else "outgoing",
                    content=f"Message {j}"
                )
        
        # Count actual usage
        conversations_count = Conversation.objects.filter(
            company=self.company,
            created_at__date=self.today
        ).count()
        
        messages_count = Message.objects.filter(
            conversation__company=self.company,
            timestamp__date=self.today
        ).count()
        
        # Create usage metrics
        metrics = UsageMetrics.objects.create(
            company=self.company,
            date=self.today,
            conversations_count=conversations_count,
            messages_count=messages_count
        )
        
        self.assertEqual(metrics.conversations_count, 5)
        self.assertEqual(metrics.messages_count, 15)  # 5 conversations × 3 messages


class BillingServiceTest(TestCase):
    """Test billing service functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Professional Plan",
            plan_type="professional",
            description="Test plan",
            price_monthly=Decimal('99.99'),
            price_yearly=Decimal('999.99'),
            max_users=25,
            max_conversations_per_month=10000,
            max_ai_requests_per_month=50000
        )

    def test_subscription_upgrade(self):
        """Test subscription plan upgrade"""
        # Start with basic subscription
        basic_plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            plan_type="starter",
            description="Basic plan",
            price_monthly=Decimal('29.99'),
            price_yearly=Decimal('299.99'),
            max_users=5,
            max_conversations_per_month=1000,
            max_ai_requests_per_month=5000
        )
        
        subscription = Subscription.objects.create(
            company=self.company,
            plan=basic_plan,
            started_at=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        # Upgrade to professional plan
        subscription.plan = self.plan
        subscription.save()
        
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.plan.price_monthly, Decimal('99.99'))

    def test_usage_limit_checking(self):
        """Test usage limit checking"""
        subscription = Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            started_at=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        # Create usage metrics
        current_usage = UsageMetrics.objects.create(
            company=self.company,
            date=date.today(),
            conversations_count=9500,  # Close to limit of 10000
            ai_requests_count=45000    # Close to limit of 50000
        )
        
        # Check if within limits
        conversations_within_limit = current_usage.conversations_count < self.plan.max_conversations_per_month
        ai_requests_within_limit = current_usage.ai_requests_count < self.plan.max_ai_requests_per_month
        
        self.assertTrue(conversations_within_limit)
        self.assertTrue(ai_requests_within_limit)
        
        # Test exceeding limits
        current_usage.conversations_count = 11000
        current_usage.ai_requests_count = 55000
        current_usage.save()
        
        conversations_within_limit = current_usage.conversations_count < self.plan.max_conversations_per_month
        ai_requests_within_limit = current_usage.ai_requests_count < self.plan.max_ai_requests_per_month
        
        self.assertFalse(conversations_within_limit)
        self.assertFalse(ai_requests_within_limit)

    def test_monthly_billing_cycle(self):
        """Test monthly billing cycle"""
        start_date = timezone.now()
        
        subscription = Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            started_at=start_date,
            current_period_start=start_date,
            current_period_end=start_date + timedelta(days=30)
        )
        
        # Create invoice for the period
        invoice = Invoice.objects.create(
            company=self.company,
            subscription=subscription,
            invoice_number="INV-2024-MONTHLY-001",
            amount=self.plan.price_monthly,
            total_amount=self.plan.price_monthly,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end
        )
        
        self.assertEqual(invoice.amount, self.plan.price_monthly)
        
        # Test period calculation
        period_length = subscription.current_period_end - subscription.current_period_start
        expected_days = 30
        actual_days = period_length.days
        
        self.assertEqual(actual_days, expected_days)

    def test_yearly_billing_cycle(self):
        """Test yearly billing cycle"""
        start_date = timezone.now()
        
        subscription = Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            started_at=start_date,
            current_period_start=start_date,
            current_period_end=start_date + timedelta(days=365)
        )
        
        # Create invoice for yearly billing
        invoice = Invoice.objects.create(
            company=self.company,
            subscription=subscription,
            invoice_number="INV-2024-YEARLY-001",
            amount=self.plan.price_yearly,
            total_amount=self.plan.price_yearly,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end
        )
        
        self.assertEqual(invoice.amount, self.plan.price_yearly)
        
        # Verify yearly discount
        monthly_equivalent = self.plan.price_monthly * 12
        self.assertLess(self.plan.price_yearly, monthly_equivalent)

    @patch('billing.models.stripe')
    def test_stripe_integration(self, mock_stripe):
        """Test Stripe integration for payments"""
        mock_stripe.Subscription.create.return_value = {
            'id': 'sub_stripe_123',
            'status': 'active'
        }
        
        mock_stripe.Invoice.create.return_value = {
            'id': 'in_stripe_123',
            'status': 'paid'
        }
        
        # Create subscription with Stripe
        subscription = Subscription.objects.create(
            company=self.company,
            plan=self.plan,
            started_at=timezone.now(),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            stripe_subscription_id="sub_stripe_123"
        )
        
        # Create invoice with Stripe
        invoice = Invoice.objects.create(
            company=self.company,
            subscription=subscription,
            invoice_number="INV-2024-STRIPE-001",
            amount=self.plan.price_monthly,
            total_amount=self.plan.price_monthly,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            stripe_invoice_id="in_stripe_123",
            status="paid"
        )
        
        self.assertEqual(subscription.stripe_subscription_id, "sub_stripe_123")
        self.assertEqual(invoice.stripe_invoice_id, "in_stripe_123")
        self.assertEqual(invoice.status, "paid")

    def test_proration_calculation(self):
        """Test proration calculation for mid-cycle upgrades"""
        # Current plan
        basic_plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            plan_type="starter",
            description="Basic plan",
            price_monthly=Decimal('29.99'),
            price_yearly=Decimal('299.99'),
            max_users=5,
            max_conversations_per_month=1000,
            max_ai_requests_per_month=5000
        )
        
        # Start subscription 15 days ago
        start_date = timezone.now() - timedelta(days=15)
        end_date = start_date + timedelta(days=30)
        
        subscription = Subscription.objects.create(
            company=self.company,
            plan=basic_plan,
            started_at=start_date,
            current_period_start=start_date,
            current_period_end=end_date
        )
        
        # Calculate proration for upgrade (15 days remaining)
        days_remaining = (end_date - timezone.now()).days
        total_days = (end_date - start_date).days
        
        old_plan_unused = (basic_plan.price_monthly * days_remaining) / total_days
        new_plan_prorated = (self.plan.price_monthly * days_remaining) / total_days
        proration_amount = new_plan_prorated - old_plan_unused
        
        # Create proration invoice
        proration_invoice = Invoice.objects.create(
            company=self.company,
            subscription=subscription,
            invoice_number="INV-2024-PRORATION-001",
            amount=proration_amount,
            total_amount=proration_amount,
            period_start=timezone.now(),
            period_end=end_date
        )
        
        self.assertGreater(proration_amount, 0)  # Should be positive for upgrade
        self.assertEqual(proration_invoice.amount, proration_amount)
