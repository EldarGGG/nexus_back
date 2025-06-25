from django.contrib import admin
from .models import BridgeConnection, BridgeCredentials, BridgeMessage, MatrixRoom, AIAssistantConfig

@admin.register(BridgeConnection)
class BridgeConnectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'platform', 'company', 'status', 'messages_sent', 'messages_received', 'created_at')
    list_filter = ('platform', 'status', 'company')
    search_fields = ('name', 'bridge_key', 'company__name')
    readonly_fields = ('bridge_key', 'created_at', 'updated_at')

@admin.register(BridgeMessage)
class BridgeMessageAdmin(admin.ModelAdmin):
    list_display = ('bridge', 'sender_name', 'direction', 'message_type', 'ai_processed', 'created_at')
    list_filter = ('direction', 'message_type', 'ai_processed', 'bridge__platform')
    search_fields = ('content', 'sender_name', 'sender_platform_id')
    readonly_fields = ('created_at',)

@admin.register(MatrixRoom)
class MatrixRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'room_type', 'company', 'bridge', 'customer_name', 'created_at')
    list_filter = ('room_type', 'company', 'bridge__platform')
    search_fields = ('name', 'customer_name', 'matrix_room_id')

@admin.register(AIAssistantConfig)
class AIAssistantConfigAdmin(admin.ModelAdmin):
    list_display = ('company', 'bridge', 'model_name', 'auto_respond', 'confidence_threshold')
    list_filter = ('model_name', 'auto_respond', 'company')