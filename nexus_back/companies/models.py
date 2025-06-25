from django.db import models
from django.core.validators import EmailValidator, URLValidator
from django.utils.text import slugify
from django.contrib.auth.hashers import make_password, check_password
import uuid
import json


class Company(models.Model):
    """
    Multi-tenant company model for B2B SaaS platform
    """
    COMPANY_SIZE_CHOICES = [
        ('startup', 'Startup (1-10 employees)'),
        ('small', 'Small (11-50 employees)'),
        ('medium', 'Medium (51-200 employees)'),
        ('large', 'Large (201-1000 employees)'),
        ('enterprise', 'Enterprise (1000+ employees)'),
    ]
    
    PLAN_CHOICES = [
        ('trial', 'Trial'),
        ('basic', 'Basic'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('cancelled', 'Cancelled'),
        ('trial_expired', 'Trial Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(unique=True, max_length=100)
    domain = models.CharField(max_length=255, unique=True, null=True, blank=True)
    
    # Contact Information
    email = models.EmailField(validators=[EmailValidator()])
    phone = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(validators=[URLValidator()], blank=True, null=True)
    
    # Company Details
    size = models.CharField(max_length=20, choices=COMPANY_SIZE_CHOICES, default='startup')
    industry = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    # Billing & Plan
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='trial')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_ends_at = models.DateTimeField(null=True, blank=True)
    
    # Settings
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    
    # Usage Limits
    max_users = models.PositiveIntegerField(default=5)
    max_bridges = models.PositiveIntegerField(default=3)
    max_ai_requests_per_month = models.PositiveIntegerField(default=1000)
    
    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'companies'
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['domain']),
            models.Index(fields=['status']),
            models.Index(fields=['plan']),
        ]

    def __str__(self):
        return self.name
    
    @property
    def users(self):
        """Get all users belonging to this company"""
        from authentication.models import CustomUser
        return CustomUser.objects.filter(company=self)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness
            original_slug = self.slug
            counter = 1
            while Company.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    @property
    def is_trial(self):
        return self.plan == 'trial'

    @property
    def is_enterprise(self):
        return self.plan == 'enterprise'


class CompanySettings(models.Model):
    """
    Company-specific configuration settings
    """
    company = models.OneToOneField(
        Company, 
        on_delete=models.CASCADE, 
        related_name='settings'
    )
    
    # AI Configuration
    ai_enabled = models.BooleanField(default=True)
    ai_provider = models.CharField(
        max_length=20, 
        choices=[('google', 'Google Gemini'), ('openai', 'OpenAI')],
        default='google'
    )
    ai_model = models.CharField(max_length=50, default='gemini-pro')
    ai_temperature = models.FloatField(default=0.7)
    ai_max_tokens = models.IntegerField(default=1000)
    
    # Message Settings
    message_retention_days = models.PositiveIntegerField(default=90)
    auto_archive_days = models.PositiveIntegerField(default=30)
    
    # Notification Settings
    email_notifications = models.BooleanField(default=True)
    webhook_url = models.URLField(blank=True, null=True)
    webhook_events = models.JSONField(default=list, blank=True)
    
    # Security Settings
    require_2fa = models.BooleanField(default=False)
    allowed_ip_ranges = models.JSONField(default=list, blank=True)
    session_timeout_minutes = models.PositiveIntegerField(default=480)  # 8 hours
    
    # Integration Settings
    matrix_room_prefix = models.CharField(max_length=50, default='company')
    auto_create_rooms = models.BooleanField(default=True)
    bridge_auto_reconnect = models.BooleanField(default=True)
    
    # Business Settings
    business_hours = models.JSONField(default=dict, blank=True)
    auto_response_enabled = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'company_settings'

    def __str__(self):
        return f"Settings for {self.company.name}"


class CompanyInvitation(models.Model):
    """
    Invitations for users to join companies
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]

    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('agent', 'Agent'),
        ('viewer', 'Viewer'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField(validators=[EmailValidator()])
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='agent')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    invited_by = models.ForeignKey(
        'authentication.CustomUser', 
        on_delete=models.CASCADE, 
        related_name='sent_invitations'
    )
    invited_user = models.ForeignKey(
        'authentication.CustomUser', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='received_invitations'
    )
    
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'company_invitations'
        unique_together = [['company', 'email']]
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['status']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Invitation to {self.email} for {self.company.name}"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            from django.utils import timezone
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(days=7)
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at


class CompanyBridgeConfiguration(models.Model):
    """
    Company-specific Matrix bridge configurations for B2B multi-tenancy
    """
    PLATFORM_CHOICES = [
        ('whatsapp', 'WhatsApp Business'),
        ('telegram', 'Telegram'),
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook Messenger'),
        ('signal', 'Signal'),
    ]
    
    STATUS_CHOICES = [
        ('configured', 'Configured'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
        ('pending', 'Pending Setup'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE, 
        related_name='bridge_configurations'
    )
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Encrypted configuration data
    encrypted_config = models.TextField(blank=True, null=True)
    
    # Platform-specific settings
    # WhatsApp Business
    whatsapp_phone_number_id = models.CharField(max_length=100, blank=True, null=True)
    whatsapp_business_account_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Telegram
    telegram_bot_username = models.CharField(max_length=100, blank=True, null=True)
    
    # Instagram/Facebook
    instagram_page_id = models.CharField(max_length=100, blank=True, null=True)
    facebook_page_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Common settings
    webhook_url = models.URLField(blank=True, null=True)
    auto_sync_enabled = models.BooleanField(default=True)
    message_encryption = models.BooleanField(default=True)
    
    # Matrix room configuration
    matrix_room_alias_prefix = models.CharField(max_length=50, blank=True, null=True)
    matrix_namespace = models.CharField(max_length=100, blank=True, null=True)
    
    # Metadata
    last_sync_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    setup_completed_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'company_bridge_configurations'
        unique_together = [['company', 'platform']]
        indexes = [
            models.Index(fields=['company', 'platform']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.company.name} - {self.get_platform_display()}"

    def set_encrypted_config(self, config_data: dict):
        """Encrypt and store sensitive configuration data"""
        try:
            from django.conf import settings
            from cryptography.fernet import Fernet
            import base64
            
            # Use company-specific encryption key or global fallback
            key_string = getattr(settings, 'BRIDGE_ENCRYPTION_KEY', 'your-32-char-encryption-key-here-12345')
            
            # Ensure key is exactly 32 bytes for Fernet
            if len(key_string) < 32:
                key_string = key_string.ljust(32, '0')
            elif len(key_string) > 32:
                key_string = key_string[:32]
            
            # Generate a Fernet key from our string
            key = base64.urlsafe_b64encode(key_string.encode()[:32])
            f = Fernet(key)
            
            config_json = json.dumps(config_data)
            encrypted_config = f.encrypt(config_json.encode())
            self.encrypted_config = encrypted_config.decode()
        except ImportError:
            # Fallback to base64 encoding if cryptography is not available
            import base64
            config_json = json.dumps(config_data)
            self.encrypted_config = base64.b64encode(config_json.encode()).decode()

    def get_decrypted_config(self) -> dict:
        """Decrypt and return configuration data"""
        if not self.encrypted_config:
            return {}
            
        try:
            from django.conf import settings
            from cryptography.fernet import Fernet
            import base64
            
            # Use same key generation as encryption
            key_string = getattr(settings, 'BRIDGE_ENCRYPTION_KEY', 'your-32-char-encryption-key-here-12345')
            
            if len(key_string) < 32:
                key_string = key_string.ljust(32, '0')
            elif len(key_string) > 32:
                key_string = key_string[:32]
            
            key = base64.urlsafe_b64encode(key_string.encode()[:32])
            f = Fernet(key)
            
            decrypted_data = f.decrypt(self.encrypted_config.encode())
            return json.loads(decrypted_data.decode())
        except ImportError:
            # Fallback to base64 decoding
            import base64
            try:
                decoded_data = base64.b64decode(self.encrypted_config.encode())
                return json.loads(decoded_data.decode())
            except Exception:
                return {}
        except Exception:
            return {}

    def get_setup_instructions(self) -> dict:
        """Get platform-specific setup instructions for the client"""
        instructions = {
            'whatsapp': {
                'title': 'WhatsApp Business API Setup',
                'steps': [
                    'Go to Meta for Developers (developers.facebook.com)',
                    'Create a new app and select "Business" type',
                    'Add WhatsApp Business API product',
                    'Generate a permanent access token',
                    'Add your phone number to the WhatsApp Business account',
                    'Configure webhook URL in your app settings'
                ],
                'required_fields': [
                    {'field': 'access_token', 'label': 'Access Token', 'type': 'password'},
                    {'field': 'phone_number_id', 'label': 'Phone Number ID', 'type': 'text'},
                    {'field': 'business_account_id', 'label': 'Business Account ID', 'type': 'text'},
                    {'field': 'webhook_verify_token', 'label': 'Webhook Verify Token', 'type': 'password'},
                ],
                'webhook_url': f'/api/webhooks/whatsapp/{self.company.id}/',
            },
            'telegram': {
                'title': 'Telegram Bot Setup',
                'steps': [
                    'Message @BotFather on Telegram',
                    'Send /newbot command',
                    'Choose a name and username for your bot',
                    'Copy the bot token provided by BotFather',
                    'Optionally set bot description and profile picture'
                ],
                'required_fields': [
                    {'field': 'bot_token', 'label': 'Bot Token', 'type': 'password'},
                    {'field': 'bot_username', 'label': 'Bot Username', 'type': 'text'},
                ],
                'webhook_url': f'/api/webhooks/telegram/{self.company.id}/',
            },
            'instagram': {
                'title': 'Instagram Business API Setup',
                'steps': [
                    'Connect your Instagram Business account to a Facebook Page',
                    'Go to Meta for Developers and create an app',
                    'Add Instagram Basic Display API product',
                    'Generate access tokens for your Instagram account',
                    'Subscribe to Instagram webhook events'
                ],
                'required_fields': [
                    {'field': 'access_token', 'label': 'Access Token', 'type': 'password'},
                    {'field': 'page_id', 'label': 'Instagram Page ID', 'type': 'text'},
                    {'field': 'app_secret', 'label': 'App Secret', 'type': 'password'},
                ],
                'webhook_url': f'/api/webhooks/instagram/{self.company.id}/',
            },
            'facebook': {
                'title': 'Facebook Messenger Setup',
                'steps': [
                    'Create a Facebook Page for your business',
                    'Go to Meta for Developers and create an app',
                    'Add Messenger API product',
                    'Generate page access token',
                    'Subscribe your app to page events'
                ],
                'required_fields': [
                    {'field': 'page_access_token', 'label': 'Page Access Token', 'type': 'password'},
                    {'field': 'page_id', 'label': 'Facebook Page ID', 'type': 'text'},
                    {'field': 'app_secret', 'label': 'App Secret', 'type': 'password'},
                ],
                'webhook_url': f'/api/webhooks/facebook/{self.company.id}/',
            },
            'signal': {
                'title': 'Signal Bot Setup',
                'steps': [
                    'Install Signal CLI on your server',
                    'Register a phone number with Signal',
                    'Link the number to Signal CLI',
                    'Generate API credentials for Signal bridge'
                ],
                'required_fields': [
                    {'field': 'phone_number', 'label': 'Signal Phone Number', 'type': 'text'},
                    {'field': 'signal_cli_path', 'label': 'Signal CLI Path', 'type': 'text'},
                    {'field': 'account_data', 'label': 'Account Data File Path', 'type': 'text'},
                ],
                'webhook_url': f'/api/webhooks/signal/{self.company.id}/',
            }
        }
        
        return instructions.get(self.platform, {})


class CompanyBridgeWebhook(models.Model):
    """
    Track webhook events for company bridge configurations
    """
    EVENT_TYPE_CHOICES = [
        ('message_received', 'Message Received'),
        ('message_delivered', 'Message Delivered'),
        ('message_read', 'Message Read'),
        ('user_joined', 'User Joined'),
        ('user_left', 'User Left'),
        ('status_update', 'Status Update'),
        ('error', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bridge_config = models.ForeignKey(
        CompanyBridgeConfiguration, 
        on_delete=models.CASCADE, 
        related_name='webhook_events'
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    event_data = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'company_bridge_webhooks'
        indexes = [
            models.Index(fields=['bridge_config', 'event_type']),
            models.Index(fields=['processed', 'created_at']),
        ]

    def __str__(self):
        return f"{self.bridge_config} - {self.get_event_type_display()}"
