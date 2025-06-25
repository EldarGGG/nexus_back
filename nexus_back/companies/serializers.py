from rest_framework import serializers
from .models import Company, CompanySettings, CompanyInvitation

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ('id', 'name', 'slug', 'logo', 'website', 'industry', 
                 'company_size', 'address', 'phone', 'subscription_plan', 
                 'trial_expires_at', 'is_active', 'created_at')
        read_only_fields = ('id', 'slug', 'subscription_plan', 'trial_expires_at', 'created_at')

class CompanyDetailSerializer(serializers.ModelSerializer):
    """Detailed company serializer with additional fields"""
    total_users = serializers.SerializerMethodField()
    active_bridges = serializers.SerializerMethodField()
    
    class Meta:
        model = Company
        fields = ('id', 'name', 'slug', 'logo', 'website', 'industry', 
                 'company_size', 'address', 'phone', 'subscription_plan', 
                 'trial_expires_at', 'is_active', 'created_at', 'total_users', 'active_bridges')
        read_only_fields = ('id', 'slug', 'subscription_plan', 'trial_expires_at', 'created_at')
    
    def get_total_users(self, obj):
        return obj.users.count()
        
    def get_active_bridges(self, obj):
        return obj.bridge_connections.filter(is_active=True).count()

class CompanySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanySettings
        fields = '__all__'
        read_only_fields = ('company',)

class CompanyInvitationSerializer(serializers.ModelSerializer):
    """Serializer for company invitations"""
    
    class Meta:
        model = CompanyInvitation
        fields = ('id', 'email', 'role', 'invited_by', 'created_at', 'expires_at', 'is_accepted')
        read_only_fields = ('id', 'invited_by', 'created_at', 'expires_at', 'is_accepted')

class CompanyOnboardingSerializer(serializers.Serializer):
    """Serializer for company onboarding process"""
    company_name = serializers.CharField(max_length=255)
    industry = serializers.CharField(max_length=100, required=False)
    company_size = serializers.CharField(max_length=50)
    website = serializers.URLField(required=False)
    logo = serializers.ImageField(required=False)
    
    # Admin user details
    admin_first_name = serializers.CharField(max_length=30)
    admin_last_name = serializers.CharField(max_length=30)
    admin_email = serializers.EmailField()
    admin_phone = serializers.CharField(max_length=20, required=False)
