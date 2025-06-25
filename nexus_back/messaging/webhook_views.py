from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.conf import settings
import json
import logging

from .services.whatsapp_service import WhatsAppService
from .services.telegram_service import TelegramService
from .services.instagram_service import InstagramService
from companies.models import Company

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(View):
    """Handle WhatsApp webhook callbacks"""
    
    def get(self, request):
        """Verify webhook (WhatsApp requirement)"""
        verify_token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if verify_token == getattr(settings, 'WHATSAPP_VERIFY_TOKEN', None):
            return HttpResponse(challenge)
        
        return HttpResponse('Invalid verify token', status=403)
    
    def post(self, request):
        """Process incoming WhatsApp messages"""
        try:
            data = json.loads(request.body)
            
            # Extract company_id from the webhook data or URL parameter
            company_id = request.GET.get('company_id')
            if not company_id:
                logger.error("No company_id provided in WhatsApp webhook")
                return JsonResponse({"error": "company_id required"}, status=400)
            
            # Process webhook
            service = WhatsAppService()
            result = service.process_webhook(data, company_id)
            
            if result.get('status') == 'processed':
                return JsonResponse({"status": "success"})
            else:
                return JsonResponse({"error": result.get('error')}, status=400)
                
        except Exception as e:
            logger.error(f"Error processing WhatsApp webhook: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TelegramWebhookView(View):
    """Handle Telegram webhook callbacks"""
    
    def post(self, request):
        """Process incoming Telegram messages"""
        try:
            data = json.loads(request.body)
            
            # Extract company_id from URL parameter
            company_id = request.GET.get('company_id')
            if not company_id:
                logger.error("No company_id provided in Telegram webhook")
                return JsonResponse({"error": "company_id required"}, status=400)
            
            # Process webhook
            service = TelegramService()
            result = service.process_webhook(data, company_id)
            
            if result.get('status') == 'processed':
                return JsonResponse({"status": "success"})
            else:
                return JsonResponse({"error": result.get('error')}, status=400)
                
        except Exception as e:
            logger.error(f"Error processing Telegram webhook: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class InstagramWebhookView(View):
    """Handle Instagram webhook callbacks"""
    
    def get(self, request):
        """Verify webhook (Instagram requirement)"""
        verify_token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if verify_token == getattr(settings, 'INSTAGRAM_VERIFY_TOKEN', None):
            return HttpResponse(challenge)
        
        return HttpResponse('Invalid verify token', status=403)
    
    def post(self, request):
        """Process incoming Instagram messages"""
        try:
            data = json.loads(request.body)
            
            # Extract company_id from URL parameter
            company_id = request.GET.get('company_id')
            if not company_id:
                logger.error("No company_id provided in Instagram webhook")
                return JsonResponse({"error": "company_id required"}, status=400)
            
            # Process webhook
            service = InstagramService()
            result = service.process_webhook(data, company_id)
            
            if result.get('status') == 'processed':
                return JsonResponse({"status": "success"})
            else:
                return JsonResponse({"error": result.get('error')}, status=400)
                
        except Exception as e:
            logger.error(f"Error processing Instagram webhook: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)
