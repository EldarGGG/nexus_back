from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import Company, CompanySettings, CompanyInvitation


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'slug', 'status', 'plan', 'size', 
        'user_count', 'created_at', 'is_active'
    ]
    list_filter = ['status', 'plan', 'size', 'is_active', 'created_at']
    search_fields = ['name', 'slug', 'email', 'domain']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['id', 'created_at', 'updated_at', 'user_count']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'slug', 'domain', 'description')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone', 'website')
        }),
        ('Company Details', {
            'fields': ('size', 'industry')
        }),
        ('Subscription & Billing', {
            'fields': ('plan', 'status', 'trial_ends_at', 'subscription_ends_at')
        }),
        ('Settings', {
            'fields': ('timezone', 'language')
        }),
        ('Usage Limits', {
            'fields': ('max_users', 'max_bridges', 'max_ai_requests_per_month')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at', 'is_active'),
            'classes': ('collapse',)
        })
    )

    def user_count(self, obj):
        count = obj.users.count()
        url = reverse('admin:authentication_customuser_changelist')
        return format_html(
            '<a href="{}?company__id={}">{} users</a>',
            url, obj.id, count
        )
    user_count.short_description = 'Users'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('users')


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = [
        'company', 'ai_enabled', 'ai_provider', 'ai_model',
        'message_retention_days', 'require_2fa'
    ]
    list_filter = ['ai_enabled', 'ai_provider', 'require_2fa', 'email_notifications']
    search_fields = ['company__name', 'company__slug']
    
    fieldsets = (
        ('Company', {
            'fields': ('company',)
        }),
        ('AI Configuration', {
            'fields': (
                'ai_enabled', 'ai_provider', 'ai_model', 
                'ai_temperature', 'ai_max_tokens'
            )
        }),
        ('Message Settings', {
            'fields': ('message_retention_days', 'auto_archive_days')
        }),
        ('Notifications', {
            'fields': ('email_notifications', 'webhook_url', 'webhook_events')
        }),
        ('Security', {
            'fields': (
                'require_2fa', 'allowed_ip_ranges', 'session_timeout_minutes'
            )
        }),
        ('Integration', {
            'fields': (
                'matrix_room_prefix', 'auto_create_rooms', 'bridge_auto_reconnect'
            )
        })
    )


@admin.register(CompanyInvitation)
class CompanyInvitationAdmin(admin.ModelAdmin):
    list_display = [
        'email', 'company', 'role', 'status', 
        'invited_by', 'created_at', 'expires_at'
    ]
    list_filter = ['status', 'role', 'created_at', 'expires_at']
    search_fields = ['email', 'company__name', 'invited_by__email']
    readonly_fields = ['id', 'token', 'created_at', 'updated_at', 'accepted_at']
    
    fieldsets = (
        ('Invitation Details', {
            'fields': ('id', 'company', 'email', 'role', 'status')
        }),
        ('Inviter Information', {
            'fields': ('invited_by', 'invited_user')
        }),
        ('Token & Expiry', {
            'fields': ('token', 'expires_at', 'accepted_at')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'company', 'invited_by', 'invited_user'
        )
