# apps/authentication/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
import uuid
from django.utils import timezone
from datetime import timedelta

class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(
        max_length=20, 
        blank=True,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Invalid phone number")]
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    is_verified = models.BooleanField(default=False)
    mfa_enabled = models.BooleanField(default=False)
    last_activity = models.DateTimeField(auto_now=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    onboarding_completed = models.BooleanField(default=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'auth_user_custom'

    def __str__(self):
        return self.username

class UserRole(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Company Owner'),
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('agent', 'Agent'),
        ('viewer', 'Viewer'),
    ]
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    permissions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user']

class MFADevice(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    device_name = models.CharField(max_length=100)
    secret_key = models.CharField(max_length=32)
    is_active = models.BooleanField(default=True)
    backup_codes = models.JSONField(default=list)
    last_used = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class EmailVerificationToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

class PasswordResetToken(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

class UserInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('expired', 'Expired'),
    ]
    
    email = models.EmailField()
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    invited_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=UserRole.ROLE_CHOICES)
    token = models.UUIDField(default=uuid.uuid4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

class LoginAttempt(models.Model):
    email = models.EmailField()
    ip_address = models.GenericIPAddressField()
    success = models.BooleanField()
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

class SecurityLog(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    action = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)


class UserSession(models.Model):
    """Track user sessions for security and analytics"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sessions')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'user_sessions'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        return f"Session for {self.user.email} from {self.ip_address}"
    
    @property
    def is_active(self):
        return self.ended_at is None