"""
Company Bridge Configuration Views - B2B Multi-tenant Bridge Setup
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils import timezone
import logging

from companies.models import Company, CompanyBridgeConfiguration, CompanyBridgeWebhook
from matrix_integration.services.matrix_bridge_service import matrix_service
from .bridge_serializers import (
    CompanyBridgeConfigurationSerializer, 
    BridgeSetupSerializer,
    BridgeTestSerializer
)

logger = logging.getLogger(__name__)


class CompanyBridgeConfigurationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing company bridge configurations"""
    permission_classes = [IsAuthenticated]
    serializer_class = CompanyBridgeConfigurationSerializer

    def get_queryset(self):
        """Filter to only company's own bridge configurations"""
        return CompanyBridgeConfiguration.objects.filter(company=self.request.user.company)

    def perform_create(self, serializer):
        """Automatically set the company when creating a new bridge config"""
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['get'])
    def platforms(self, request):
        """Get available platforms and their current status"""
        company = request.user.company
        platforms = []
        
        for platform_code, platform_name in CompanyBridgeConfiguration.PLATFORM_CHOICES:
            try:
                config = CompanyBridgeConfiguration.objects.get(
                    company=company, 
                    platform=platform_code
                )
                platform_info = {
                    'code': platform_code,
                    'name': platform_name,
                    'status': config.status,
                    'configured': True,
                    'last_sync': config.last_sync_at.isoformat() if config.last_sync_at else None,
                    'setup_completed': config.setup_completed_at.isoformat() if config.setup_completed_at else None,
                    'config_id': str(config.id)
                }
            except CompanyBridgeConfiguration.DoesNotExist:
                platform_info = {
                    'code': platform_code,
                    'name': platform_name,
                    'status': 'not_configured',
                    'configured': False,
                    'last_sync': None,
                    'setup_completed': None,
                    'config_id': None
                }
            
            platforms.append(platform_info)
        
        return Response({
            'platforms': platforms,
            'company': {
                'id': str(company.id),
                'name': company.name,
                'plan': company.plan
            }
        })

    @action(detail=False, methods=['post'])
    def setup(self, request):
        """Initialize setup for a new platform bridge"""
        platform = request.data.get('platform')
        
        if not platform:
            return Response(
                {'error': 'Platform is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if platform not in dict(CompanyBridgeConfiguration.PLATFORM_CHOICES):
            return Response(
                {'error': 'Invalid platform'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        company = request.user.company
        
        # Check if already exists
        config, created = CompanyBridgeConfiguration.objects.get_or_create(
            company=company,
            platform=platform,
            defaults={
                'status': 'pending',
                'matrix_namespace': f"{company.slug}_{platform}",
                'matrix_room_alias_prefix': f"{company.slug}_{platform}"
            }
        )
        
        if not created and config.status == 'active':
            return Response(
                {'error': 'Platform already configured and active'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get setup instructions
        instructions = config.get_setup_instructions()
        
        return Response({
            'status': 'setup_initialized',
            'config_id': str(config.id),
            'platform': platform,
            'instructions': instructions,
            'next_step': 'configure'
        })

    @action(detail=True, methods=['post'])
    def configure(self, request, pk=None):
        """Configure bridge with platform credentials"""
        config = self.get_object()
        serializer = BridgeSetupSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Store encrypted configuration
            config_data = serializer.validated_data.copy()
            config.set_encrypted_config(config_data)
            
            # Update platform-specific fields
            if config.platform == 'whatsapp':
                config.whatsapp_phone_number_id = config_data.get('phone_number_id')
                config.whatsapp_business_account_id = config_data.get('business_account_id')
            elif config.platform == 'telegram':
                config.telegram_bot_username = config_data.get('bot_username')
            elif config.platform == 'instagram':
                config.instagram_page_id = config_data.get('page_id')
            elif config.platform == 'facebook':
                config.facebook_page_id = config_data.get('page_id')
            
            config.status = 'configured'
            config.error_message = None
            config.save()
            
            logger.info(f"Bridge configured for {config.company.name} - {config.platform}")
            
            return Response({
                'status': 'configured',
                'message': f'{config.get_platform_display()} bridge configured successfully',
                'next_step': 'test'
            })
            
        except Exception as e:
            logger.error(f"Error configuring bridge {config.id}: {e}")
            config.status = 'error'
            config.error_message = str(e)
            config.save()
            
            return Response(
                {'error': f'Failed to configure bridge: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test bridge configuration"""
        config = self.get_object()
        serializer = BridgeTestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        test_data = serializer.validated_data
        
        try:
            # Test the bridge connection
            test_result = self._test_bridge_connection(config, test_data)
            
            if test_result['success']:
                config.status = 'active'
                config.setup_completed_at = timezone.now()
                config.last_sync_at = timezone.now()
                config.error_message = None
                config.save()
                
                # Initialize Matrix bridge for this company/platform
                matrix_service.initialize_company_bridge(
                    company_id=str(config.company.id),
                    platform=config.platform,
                    config_data=config.get_decrypted_config()
                )
                
                return Response({
                    'status': 'active',
                    'message': f'{config.get_platform_display()} bridge is now active',
                    'test_result': test_result
                })
            else:
                config.status = 'error'
                config.error_message = test_result.get('error', 'Test failed')
                config.save()
                
                return Response({
                    'status': 'error',
                    'error': test_result.get('error', 'Test failed'),
                    'test_result': test_result
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error testing bridge {config.id}: {e}")
            config.status = 'error'
            config.error_message = str(e)
            config.save()
            
            return Response(
                {'error': f'Failed to test bridge: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a configured bridge"""
        config = self.get_object()
        
        if config.status != 'configured':
            return Response(
                {'error': 'Bridge must be configured before activation'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Initialize Matrix bridge
            matrix_service.initialize_company_bridge(
                company_id=str(config.company.id),
                platform=config.platform,
                config_data=config.get_decrypted_config()
            )
            
            config.status = 'active'
            config.setup_completed_at = timezone.now()
            config.last_sync_at = timezone.now()
            config.save()
            
            return Response({
                'status': 'active',
                'message': f'{config.get_platform_display()} bridge activated successfully'
            })
            
        except Exception as e:
            logger.error(f"Error activating bridge {config.id}: {e}")
            return Response(
                {'error': f'Failed to activate bridge: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a bridge"""
        config = self.get_object()
        
        config.status = 'inactive'
        config.save()
        
        return Response({
            'status': 'inactive',
            'message': f'{config.get_platform_display()} bridge deactivated'
        })

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get detailed status of a bridge"""
        config = self.get_object()
        
        # Get recent webhook events
        recent_events = CompanyBridgeWebhook.objects.filter(
            bridge_config=config
        ).order_by('-created_at')[:10]
        
        webhook_events = []
        for event in recent_events:
            webhook_events.append({
                'type': event.event_type,
                'processed': event.processed,
                'created_at': event.created_at.isoformat(),
                'error': event.processing_error
            })
        
        return Response({
            'id': str(config.id),
            'platform': config.platform,
            'status': config.status,
            'last_sync': config.last_sync_at.isoformat() if config.last_sync_at else None,
            'setup_completed': config.setup_completed_at.isoformat() if config.setup_completed_at else None,
            'error_message': config.error_message,
            'recent_events': webhook_events,
            'matrix_namespace': config.matrix_namespace,
            'webhook_url': config.webhook_url
        })

    def _test_bridge_connection(self, config, test_data):
        """Test platform-specific bridge connection"""
        platform = config.platform
        config_data = config.get_decrypted_config()
        
        try:
            if platform == 'whatsapp':
                return self._test_whatsapp_connection(config_data, test_data)
            elif platform == 'telegram':
                return self._test_telegram_connection(config_data, test_data)
            elif platform == 'instagram':
                return self._test_instagram_connection(config_data, test_data)
            elif platform == 'facebook':
                return self._test_facebook_connection(config_data, test_data)
            elif platform == 'signal':
                return self._test_signal_connection(config_data, test_data)
            else:
                return {'success': False, 'error': 'Unsupported platform'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _test_whatsapp_connection(self, config_data, test_data):
        """Test WhatsApp Business API connection"""
        import requests
        
        access_token = config_data.get('access_token')
        phone_number_id = config_data.get('phone_number_id')
        
        if not access_token or not phone_number_id:
            return {'success': False, 'error': 'Missing access token or phone number ID'}
        
        # Test API connection
        url = f"https://graph.facebook.com/v18.0/{phone_number_id}"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return {'success': True, 'message': 'WhatsApp API connection successful'}
        else:
            return {'success': False, 'error': f'API test failed: {response.text}'}

    def _test_telegram_connection(self, config_data, test_data):
        """Test Telegram Bot API connection"""
        import requests
        
        bot_token = config_data.get('bot_token')
        
        if not bot_token:
            return {'success': False, 'error': 'Missing bot token'}
        
        # Test bot API
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        response = requests.get(url)
        
        if response.status_code == 200:
            bot_info = response.json()
            return {
                'success': True, 
                'message': 'Telegram bot connection successful',
                'bot_info': bot_info.get('result', {})
            }
        else:
            return {'success': False, 'error': f'Bot API test failed: {response.text}'}

    def _test_instagram_connection(self, config_data, test_data):
        """Test Instagram API connection"""
        import requests
        
        access_token = config_data.get('access_token')
        page_id = config_data.get('page_id')
        
        if not access_token or not page_id:
            return {'success': False, 'error': 'Missing access token or page ID'}
        
        # Test Instagram Basic Display API
        url = f"https://graph.facebook.com/v18.0/{page_id}"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return {'success': True, 'message': 'Instagram API connection successful'}
        else:
            return {'success': False, 'error': f'API test failed: {response.text}'}

    def _test_facebook_connection(self, config_data, test_data):
        """Test Facebook Messenger API connection"""
        import requests
        
        page_access_token = config_data.get('page_access_token')
        page_id = config_data.get('page_id')
        
        if not page_access_token or not page_id:
            return {'success': False, 'error': 'Missing page access token or page ID'}
        
        # Test Messenger API
        url = f"https://graph.facebook.com/v18.0/{page_id}"
        headers = {'Authorization': f'Bearer {page_access_token}'}
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return {'success': True, 'message': 'Facebook Messenger API connection successful'}
        else:
            return {'success': False, 'error': f'API test failed: {response.text}'}

    def _test_signal_connection(self, config_data, test_data):
        """Test Signal CLI connection"""
        import subprocess
        
        signal_cli_path = config_data.get('signal_cli_path', 'signal-cli')
        phone_number = config_data.get('phone_number')
        
        if not phone_number:
            return {'success': False, 'error': 'Missing phone number'}
        
        try:
            # Test signal-cli installation and account
            result = subprocess.run([
                signal_cli_path, '--account', phone_number, 'listIdentities'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return {'success': True, 'message': 'Signal CLI connection successful'}
            else:
                return {'success': False, 'error': f'Signal CLI test failed: {result.stderr}'}
                
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Signal CLI test timed out'}
        except Exception as e:
            return {'success': False, 'error': f'Signal CLI test error: {str(e)}'}
