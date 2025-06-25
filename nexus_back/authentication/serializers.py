from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import CustomUser, UserRole, EmailVerificationToken, MFADevice
from companies.models import Company, CompanySettings

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    company_name = serializers.CharField(write_only=True)
    industry = serializers.CharField(write_only=True, required=False)
    company_size = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'phone', 
                 'password', 'password_confirm', 'company_name', 'industry', 'company_size')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        # Extract company data
        company_data = {
            'name': validated_data.pop('company_name'),
            'industry': validated_data.pop('industry'),
            'company_size': validated_data.pop('company_size'),
        }
        
        # Remove password confirmation
        validated_data.pop('password_confirm')
        
        # Create company
        company = Company.objects.create(**company_data)
        
        # Create user
        user = CustomUser.objects.create_user(
            company=company,
            **validated_data
        )
        
        # Create user role as company owner
        UserRole.objects.create(
            user=user,
            role='owner',
            permissions={
                'can_manage_users': True,
                'can_manage_settings': True,
                'can_view_analytics': True,
                'can_manage_integrations': True
            }
        )
        
        # Create company settings
        CompanySettings.objects.create(company=company)
        
        return user

class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Must include username and password')
        
        return attrs

class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 
                 'phone', 'avatar', 'timezone', 'is_verified', 'role', 'company_name')

    def get_role(self, obj):
        try:
            return obj.userrole.role
        except UserRole.DoesNotExist:
            return None

    def get_company_name(self, obj):
        return obj.company.name if obj.company else None

class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

class UserInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=UserRole.ROLE_CHOICES)

class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile updates"""
    
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'phone', 'avatar', 'timezone')
        
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class MFADeviceSerializer(serializers.ModelSerializer):
    """Serializer for MFA devices"""
    
    class Meta:
        model = MFADevice
        fields = ('id', 'name', 'device_type', 'is_active', 'created_at')
        read_only_fields = ('id', 'created_at')

class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change (alias for PasswordChangeSerializer)"""
    current_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs
