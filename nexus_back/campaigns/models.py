from django.db import models
import uuid
from django.contrib.auth import get_user_model

User = get_user_model()

class Campaign(models.Model):
    """Marketing/messaging campaigns"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='campaigns')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    platform = models.CharField(max_length=50)  # whatsapp, telegram, etc.
    message_template = models.TextField()
    target_audience = models.JSONField(default=dict)  # Filtering criteria
    schedule_type = models.CharField(max_length=20, default='immediate')  # immediate, scheduled, recurring
    scheduled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company.name} - {self.name}"

class CampaignRecipient(models.Model):
    """Individual recipients in a campaign"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
    ]

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='recipients')
    recipient_id = models.CharField(max_length=255)  # Phone number, user ID, etc.
    recipient_data = models.JSONField(default=dict)  # Name, etc.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        unique_together = ['campaign', 'recipient_id']

    def __str__(self):
        return f"{self.campaign.name} - {self.recipient_id}"
