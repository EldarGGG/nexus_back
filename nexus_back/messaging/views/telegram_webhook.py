"""
Telegram webhook handler views
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from asgiref.sync import async_to_sync
import asyncio

from ..services.ai_telegram_service import AITelegramService
from companies.models import Company

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def telegram_webhook(request, company_id):
    """Process incoming Telegram webhook updates"""
    try:
        # Parse JSON body
        data = json.loads(request.body)
        logger.info(f"Received Telegram webhook: {data}")
        
        # Process with AI Telegram service
        service = AITelegramService()
        result = async_to_sync(service.process_incoming_message)(data, company_id)
        
        return JsonResponse({"success": True, "result": result})
    except Exception as e:
        logger.exception(f"Error processing Telegram webhook: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@csrf_exempt
def telegram_ai_settings(request, company_id):
    """Get or update AI settings for Telegram bot"""
    try:
        service = AITelegramService()
        
        # Get current settings
        if request.method == "GET":
            settings = service.get_ai_settings(company_id)
            return JsonResponse(settings)
        
        # Update settings
        elif request.method == "POST":
            data = json.loads(request.body)
            result = service.update_ai_settings(data, company_id)
            return JsonResponse(result)
        
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)
    except Exception as e:
        logger.exception(f"Error with AI settings: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
