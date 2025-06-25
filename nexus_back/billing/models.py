from django.db import models
import uuid
from decimal import Decimal

class SubscriptionPlan(models.Model):
    """Available subscription plans"""
    PLAN_TYPES = [
        ('starter', 'Starter'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
        ('custom', 'Custom'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    description = models.TextField()
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2)
    max_users = models.IntegerField()
    max_conversations_per_month = models.IntegerField()
    max_ai_requests_per_month = models.IntegerField()
    features = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Subscription(models.Model):
    """Company subscriptions"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.OneToOneField('companies.Company', on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    started_at = models.DateTimeField()
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    is_trial = models.BooleanField(default=False)
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.company.name} - {self.plan.name}"

class Invoice(models.Model):
    """Billing invoices"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='invoices')
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    stripe_invoice_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.invoice_number} - {self.company.name}"

class UsageMetrics(models.Model):
    """Track usage for billing purposes"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='usage_metrics')
    date = models.DateField()
    conversations_count = models.IntegerField(default=0)
    messages_count = models.IntegerField(default=0)
    ai_requests_count = models.IntegerField(default=0)
    storage_used_mb = models.FloatField(default=0.0)

    class Meta:
        unique_together = ['company', 'date']

    def __str__(self):
        return f"{self.company.name} - {self.date}"
