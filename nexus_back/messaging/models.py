from django.db import models
import uuid
from django.contrib.auth import get_user_model

User = get_user_model()

class Conversation(models.Model):
    """Represents a conversation thread"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='conversations')
    external_id = models.CharField(max_length=255, blank=True)  # ID from external platform
    platform = models.CharField(max_length=50)  # whatsapp, telegram, etc.
    participants = models.JSONField(default=list)  # List of participant data
    status = models.CharField(max_length=20, default='active')
    assigned_agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['company', 'external_id', 'platform']

    def __str__(self):
        return f"{self.platform} - {self.external_id}"

class Message(models.Model):
    """Individual message in a conversation"""
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('location', 'Location'),
        ('contact', 'Contact'),
    ]
    
    DIRECTION_CHOICES = [
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    sender_info = models.JSONField(default=dict)  # External sender data
    attachments = models.JSONField(default=list)  # File attachments
    metadata = models.JSONField(default=dict)
    is_processed = models.BooleanField(default=False)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.direction} - {self.message_type} - {self.timestamp}"

class MessageTemplate(models.Model):
    """Pre-defined message templates"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='message_templates')
    name = models.CharField(max_length=100)
    content = models.TextField()
    variables = models.JSONField(default=list)  # Template variables
    category = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company.name} - {self.name}"
