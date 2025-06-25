from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from .models import CustomUser, UserRole, MFADevice, UserSession


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = [
        'email', 'first_name', 'last_name', 'company', 
        'get_role', 'mfa_enabled', 'is_active', 'last_login'
    ]
    list_filter = ['is_active', 'mfa_enabled', 'company', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['email']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {
            'fields': ('first_name', 'last_name', 'phone', 'avatar', 'timezone')
        }),
        ('Company', {
            'fields': ('company',)
        }),
        ('Security', {
            'fields': ('mfa_enabled', 'is_verified', 'email_verified', 'phone_verified')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined', 'last_activity')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ['last_login', 'date_joined', 'last_activity']

    def get_role(self, obj):
        try:
            return obj.userrole.role
        except UserRole.DoesNotExist:
            return '-'
    get_role.short_description = 'Role'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('company')


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(MFADevice)
class MFADeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'device_name', 'is_active', 'created_at', 'last_used']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'device_name']
    readonly_fields = ['secret_key', 'created_at', 'last_used']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'ip_address', 'user_agent_short', 
        'created_at', 'last_activity', 'ended_at'
    ]
    list_filter = ['created_at', 'ended_at']
    search_fields = ['user__email', 'ip_address']
    readonly_fields = ['created_at', 'last_activity', 'ended_at']
    
    def user_agent_short(self, obj):
        if obj.user_agent:
            return obj.user_agent[:50] + '...' if len(obj.user_agent) > 50 else obj.user_agent
        return '-'
    user_agent_short.short_description = 'User Agent'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')