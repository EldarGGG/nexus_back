from django.db import models
import uuid
from django.contrib.auth import get_user_model

User = get_user_model()

class AutomationRule(models.Model):
    """Automation rules for message handling"""
    TRIGGER_TYPES = [
        ('keyword', 'Keyword Match'),
        ('intent', 'Intent Recognition'),
        ('business_hours', 'Business Hours'),
        ('new_conversation', 'New Conversation'),
        ('inactivity', 'Inactivity'),
    ]

    ACTION_TYPES = [
        ('send_message', 'Send Message'),
        ('assign_agent', 'Assign Agent'),
        ('tag_conversation', 'Tag Conversation'),
        ('escalate', 'Escalate'),
        ('ai_response', 'AI Response'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='automation_rules')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    trigger_type = models.CharField(max_length=50, choices=TRIGGER_TYPES)
    trigger_conditions = models.JSONField(default=dict)  # Conditions for triggering
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    action_parameters = models.JSONField(default=dict)  # Parameters for the action
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)  # Higher number = higher priority
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'created_at']

    def __str__(self):
        return f"{self.company.name} - {self.name}"

class AutomationExecution(models.Model):
    """Log of automation rule executions"""
    rule = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name='executions')
    conversation = models.ForeignKey('messaging.Conversation', on_delete=models.CASCADE)
    message = models.ForeignKey('messaging.Message', on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')  # pending, success, failed
    result = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rule.name} - {self.status}"
