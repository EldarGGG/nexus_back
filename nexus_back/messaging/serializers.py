from rest_framework import serializers
from .models import Conversation, Message, MessageTemplate


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for Conversation model"""
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'company', 'external_id', 'platform', 'status', 
            'assigned_to', 'priority', 'tags', 'metadata',
            'last_message_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at']


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model"""
    
    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'content', 'message_type',
            'direction', 'platform_message_id', 'attachments', 'metadata',
            'is_read', 'read_at', 'ai_response', 'ai_confidence', 
            'ai_intent', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'conversation', 'sender', 'platform_message_id',
            'ai_response', 'ai_confidence', 'ai_intent', 'created_at', 'updated_at'
        ]


class MessageTemplateSerializer(serializers.ModelSerializer):
    """Serializer for MessageTemplate model"""
    
    class Meta:
        model = MessageTemplate
        fields = [
            'id', 'company', 'name', 'content', 'variables',
            'category', 'is_active', 'usage_count', 'created_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'company', 'usage_count', 'created_by', 
            'created_at', 'updated_at'
        ]
