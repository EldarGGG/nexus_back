from django.db import models
from django.contrib.auth.models import User
import uuid
import json
from cryptography.fernet import Fernet
from django.conf import settings

class BridgeConnection(models.Model):
    PLATFORM_CHOICES = [
        ('whatsapp', 'WhatsApp Business'),
        ('telegram', 'Telegram'),
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook Messenger'),
        ('signal', 'Signal'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Setup'),
        ('authenticating', 'Authenticating'),
        ('connected', 'Connected'),
        ('error', 'Error'),
        ('disconnected', 'Disconnected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='bridges')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    name = models.CharField(max_length=100)  # User-defined name like "Customer Support WhatsApp"
    
    # Unique identifier for this bridge connection
    bridge_key = models.CharField(max_length=50, unique=True)  # Auto-generated: wa_company123_uuid
    
    # Matrix integration
    matrix_room_id = models.CharField(max_length=255, blank=True)  # Main company room
    matrix_space_id = models.CharField(max_length=255, blank=True)  # Company space
    
    # Platform-specific settings
    webhook_url = models.URLField(blank=True)  # For webhook-based platforms
    webhook_secret = models.CharField(max_length=100, blank=True)
    
    # Connection status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    last_connected = models.DateTimeField(null=True, blank=True)
    
    # Usage stats
    messages_sent = models.IntegerField(default=0)
    messages_received = models.IntegerField(default=0)
    last_activity = models.DateTimeField(null=True, blank=True)
    
    # Configuration
    auto_reply_enabled = models.BooleanField(default=False)
    ai_assistant_enabled = models.BooleanField(default=True)
    business_hours_only = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['company', 'platform', 'name']
    
    def save(self, *args, **kwargs):
        if not self.bridge_key:
            # Generate unique bridge key: platform_companyslug_randomid
            random_id = str(uuid.uuid4())[:8]
            self.bridge_key = f"{self.platform}_{self.company.slug}_{random_id}"
        super().save(*args, **kwargs)

class BridgeCredentials(models.Model):
    """Encrypted credentials for each bridge connection"""
    bridge = models.OneToOneField(BridgeConnection, on_delete=models.CASCADE, related_name='credentials')
    
    # Encrypted JSON field containing all platform-specific credentials
    encrypted_data = models.TextField()
    
    # Metadata
    encryption_version = models.CharField(max_length=10, default='v1')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def encrypt_credentials(self, data):
        """Encrypt credential data"""
        fernet = Fernet(settings.BRIDGE_ENCRYPTION_KEY.encode())
        encrypted = fernet.encrypt(json.dumps(data).encode())
        self.encrypted_data = encrypted.decode()
    
    def decrypt_credentials(self):
        """Decrypt credential data"""
        fernet = Fernet(settings.BRIDGE_ENCRYPTION_KEY.encode())
        decrypted = fernet.decrypt(self.encrypted_data.encode())
        return json.loads(decrypted.decode())

class MatrixRoom(models.Model):
    """Track Matrix rooms for conversations"""
    ROOM_TYPE_CHOICES = [
        ('space', 'Company Space'),
        ('bridge', 'Bridge Room'),
        ('conversation', 'Customer Conversation'),
        ('internal', 'Internal Team Chat'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    bridge = models.ForeignKey(BridgeConnection, on_delete=models.CASCADE, null=True, blank=True)
    
    # Matrix identifiers
    matrix_room_id = models.CharField(max_length=255, unique=True)
    room_alias = models.CharField(max_length=255, blank=True)
    
    # Room metadata
    room_type = models.CharField(max_length=20, choices=ROOM_TYPE_CHOICES)
    name = models.CharField(max_length=200)
    topic = models.TextField(blank=True)
    
    # Customer info (for conversation rooms)
    customer_platform_id = models.CharField(max_length=255, blank=True)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_metadata = models.JSONField(default=dict)
    
    # Room settings
    is_encrypted = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    ai_enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class BridgeMessage(models.Model):
    """Track messages through bridges"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    bridge = models.ForeignKey(BridgeConnection, on_delete=models.CASCADE)
    matrix_room = models.ForeignKey(MatrixRoom, on_delete=models.CASCADE, null=True)
    conversation = models.ForeignKey('messaging.Conversation', on_delete=models.CASCADE, null=True)
    
    # Message identifiers
    external_message_id = models.CharField(max_length=255)  # Platform's message ID
    matrix_event_id = models.CharField(max_length=255, blank=True)  # Matrix event ID
    
    # Message content
    content = models.TextField()
    message_type = models.CharField(max_length=50)  # text, image, file, etc.
    raw_content = models.JSONField(default=dict)  # Original message data
    
    # Direction
    direction = models.CharField(max_length=10, choices=[('inbound', 'Inbound'), ('outbound', 'Outbound')])
    
    # Sender info
    sender_platform_id = models.CharField(max_length=255)  # Phone number, user ID, etc.
    sender_name = models.CharField(max_length=255, blank=True)
    sender_matrix_id = models.CharField(max_length=255, blank=True)
    
    # AI Processing
    ai_processed = models.BooleanField(default=False)
    ai_response = models.TextField(blank=True)
    ai_confidence = models.FloatField(null=True, blank=True)
    
    # Processing status
    processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

class AIAssistantConfig(models.Model):
    """AI assistant configuration per company/bridge"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    bridge = models.ForeignKey(BridgeConnection, on_delete=models.CASCADE, null=True, blank=True)
    
    # AI Settings
    model_name = models.CharField(max_length=100, default='gemini-pro')
    system_prompt = models.TextField(default="You are a helpful customer service assistant.")
    max_tokens = models.IntegerField(default=1000)
    temperature = models.FloatField(default=0.7)
    
    # Behavior settings
    auto_respond = models.BooleanField(default=False)
    escalate_to_human = models.BooleanField(default=True)
    confidence_threshold = models.FloatField(default=0.8)
    
    # Response settings
    response_delay_seconds = models.IntegerField(default=2)
    typing_indicator = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class BridgeWebhook(models.Model):
    """Store webhook events for processing"""
    bridge = models.ForeignKey(BridgeConnection, on_delete=models.CASCADE)
    
    # Webhook data
    raw_data = models.JSONField()  # Original webhook payload
    processed = models.BooleanField(default=False)
    
    # Processing info
    processing_attempts = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)