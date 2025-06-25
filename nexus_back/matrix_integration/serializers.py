from rest_framework import serializers
from .models import BridgeConnection, BridgeCredentials, BridgeMessage, MatrixRoom, AIAssistantConfig

class BridgeConnectionSerializer(serializers.ModelSerializer):
    credentials = serializers.SerializerMethodField()
    message_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = BridgeConnection
        fields = ['id', 'platform', 'name', 'bridge_key', 'status', 'error_message',
                 'last_connected', 'messages_sent', 'messages_received', 'last_activity',
                 'auto_reply_enabled', 'ai_assistant_enabled', 'business_hours_only',
                 'credentials', 'message_stats', 'created_at']
        read_only_fields = ['id', 'bridge_key', 'company', 'created_at']
    
    def get_credentials(self, obj):
        # Don't expose actual credentials in API
        return {'configured': hasattr(obj, 'credentials')}
    
    def get_message_stats(self, obj):
        return {
            'total_sent': obj.messages_sent,
            'total_received': obj.messages_received,
            'last_activity': obj.last_activity
        }

class BridgeCredentialsSerializer(serializers.ModelSerializer):
    platform_data = serializers.JSONField(write_only=True)
    
    class Meta:
        model = BridgeCredentials
        fields = ['platform_data']
    
    def create(self, validated_data):
        bridge = validated_data.pop('bridge')
        platform_data = validated_data.pop('platform_data')
        
        credentials = BridgeCredentials.objects.create(bridge=bridge)
        credentials.encrypt_credentials(platform_data)
        credentials.save()
        
        return credentials

class WhatsAppConnectionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    phone_number_id = serializers.CharField(max_length=100)
    access_token = serializers.CharField(max_length=500)

class TelegramConnectionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    bot_token = serializers.CharField(max_length=200)

class BridgeMessageSerializer(serializers.ModelSerializer):
    sender_info = serializers.SerializerMethodField()
    
    class Meta:
        model = BridgeMessage
        fields = ['id', 'content', 'message_type', 'direction', 'sender_platform_id',
                 'sender_name', 'ai_processed', 'ai_response', 'ai_confidence',
                 'sender_info', 'created_at']
    
    def get_sender_info(self, obj):
        return {
            'platform_id': obj.sender_platform_id,
            'name': obj.sender_name,
            'platform': obj.bridge.platform
        }

class AIAssistantConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIAssistantConfig
        fields = ['model_name', 'system_prompt', 'max_tokens', 'temperature',
                 'auto_respond', 'escalate_to_human', 'confidence_threshold',
                 'response_delay_seconds', 'typing_indicator']

class SendMessageSerializer(serializers.Serializer):
    customer_id = serializers.CharField(max_length=255)
    content = serializers.CharField()
    message_type = serializers.CharField(default='text')