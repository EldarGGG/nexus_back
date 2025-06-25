"""
Bridge Configuration Serializers - B2B Multi-tenant Bridge Setup
"""
from rest_framework import serializers
from companies.models import CompanyBridgeConfiguration, CompanyBridgeWebhook


class CompanyBridgeConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for bridge configuration"""
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    setup_instructions = serializers.SerializerMethodField()

    class Meta:
        model = CompanyBridgeConfiguration
        fields = [
            'id', 'platform', 'platform_display', 'status', 'status_display',
            'whatsapp_phone_number_id', 'whatsapp_business_account_id',
            'telegram_bot_username', 'instagram_page_id', 'facebook_page_id',
            'webhook_url', 'auto_sync_enabled', 'message_encryption',
            'matrix_room_alias_prefix', 'matrix_namespace',
            'last_sync_at', 'error_message', 'setup_completed_at',
            'created_at', 'updated_at', 'setup_instructions'
        ]
        read_only_fields = [
            'id', 'last_sync_at', 'setup_completed_at', 'created_at', 'updated_at'
        ]

    def get_setup_instructions(self, obj):
        """Get setup instructions for the platform"""
        return obj.get_setup_instructions()


class BridgeSetupSerializer(serializers.Serializer):
    """Serializer for bridge configuration data"""
    
    # WhatsApp fields
    access_token = serializers.CharField(required=False, write_only=True)
    phone_number_id = serializers.CharField(required=False)
    business_account_id = serializers.CharField(required=False)
    webhook_verify_token = serializers.CharField(required=False, write_only=True)
    
    # Telegram fields
    bot_token = serializers.CharField(required=False, write_only=True)
    bot_username = serializers.CharField(required=False)
    
    # Instagram fields
    page_id = serializers.CharField(required=False)
    app_secret = serializers.CharField(required=False, write_only=True)
    
    # Facebook fields
    page_access_token = serializers.CharField(required=False, write_only=True)
    
    # Signal fields
    phone_number = serializers.CharField(required=False)
    signal_cli_path = serializers.CharField(required=False, default='signal-cli')
    account_data = serializers.CharField(required=False)
    
    def validate(self, data):
        """Validate platform-specific required fields"""
        # This would be called from the view with platform context
        # For now, just return the data as-is
        return data


class BridgeTestSerializer(serializers.Serializer):
    """Serializer for testing bridge configuration"""
    test_message = serializers.CharField(
        required=False, 
        default="Test message from Nexus Bridge",
        help_text="Optional test message to send"
    )
    test_recipient = serializers.CharField(
        required=False,
        help_text="Optional test recipient (phone number, username, etc.)"
    )
    skip_message_test = serializers.BooleanField(
        default=False,
        help_text="Skip sending test message, only test API connection"
    )


class BridgeWebhookEventSerializer(serializers.ModelSerializer):
    """Serializer for bridge webhook events"""
    
    class Meta:
        model = CompanyBridgeWebhook
        fields = [
            'id', 'event_type', 'event_data', 'processed', 
            'processing_error', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BridgeStatusSerializer(serializers.Serializer):
    """Serializer for bridge status information"""
    platform = serializers.CharField()
    status = serializers.CharField()
    last_sync = serializers.DateTimeField(allow_null=True)
    setup_completed = serializers.DateTimeField(allow_null=True)
    error_message = serializers.CharField(allow_null=True)
    recent_events = BridgeWebhookEventSerializer(many=True)
    matrix_namespace = serializers.CharField(allow_null=True)
    webhook_url = serializers.URLField(allow_null=True)
