from django.db import models
import uuid
from django.contrib.auth import get_user_model

User = get_user_model()

class Integration(models.Model):
    """Third-party integrations available"""
    INTEGRATION_TYPES = [
        ('webhook', 'Webhook'),
        ('api', 'API'),
        ('oauth', 'OAuth'),
        ('websocket', 'WebSocket'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField()
    integration_type = models.CharField(max_length=20, choices=INTEGRATION_TYPES)
    icon = models.ImageField(upload_to='integrations/', blank=True)
    documentation_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    configuration_schema = models.JSONField(default=dict)  # JSON schema for config
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class CompanyIntegration(models.Model):
    """Company-specific integration configurations"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='integrations')
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # User-defined name
    configuration = models.JSONField(default=dict)  # Integration-specific config
    credentials = models.JSONField(default=dict)  # Encrypted credentials
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    last_sync = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['company', 'integration', 'name']

    def __str__(self):
        return f"{self.company.name} - {self.integration.name}"

class IntegrationLog(models.Model):
    """Log integration activities"""
    LOG_LEVELS = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ]

    company_integration = models.ForeignKey(CompanyIntegration, on_delete=models.CASCADE, related_name='logs')
    level = models.CharField(max_length=20, choices=LOG_LEVELS)
    message = models.TextField()
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.company_integration.name} - {self.level} - {self.timestamp}"
