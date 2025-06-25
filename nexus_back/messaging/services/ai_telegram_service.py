"""
AI-powered Telegram Bot Service
"""
import json
import logging
import asyncio
from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async
from typing import Dict, Any, List, Optional

from ..models import Conversation, Message
from companies.models import Company
from .telegram_service import TelegramService

logger = logging.getLogger(__name__)

class AITelegramService:
    """Service for integrating Telegram Bot with AI Assistant"""

    def __init__(self):
        self.telegram_service = TelegramService()
        # Load AI settings - in production these should be stored in database per company
        self._load_ai_settings()
        
    def _load_ai_settings(self):
        """Load AI assistant settings from configuration file or environment"""
        # Default settings
        self.ai_settings = {
            "enabled": False,
            "api_key": getattr(settings, 'OPENAI_API_KEY', ''),
            "model": "gpt-4-turbo",
            "system_prompt": (
                "Вы - вежливый и профессиональный ассистент компании. "
                "Отвечайте кратко, информативно и дружелюбно. "
                "Если вы не знаете ответа, честно признайтесь в этом."
            ),
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        # Try to load from JSON file if exists
        try:
            with open(settings.BASE_DIR / 'ai_assistant_settings.json', 'r', encoding='utf-8') as f:
                self.ai_settings.update(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning("AI assistant settings file not found or invalid, using defaults")

    async def process_incoming_message(self, update_data: Dict[str, Any], company_id: str) -> Dict[str, Any]:
        """
        Process incoming Telegram webhook update
        """
        try:
            # Extract message data
            message = update_data.get('message', {})
            chat_id = str(message.get('chat', {}).get('id'))
            user_id = str(message.get('from', {}).get('id'))
            username = message.get('from', {}).get('username', '')
            first_name = message.get('from', {}).get('first_name', '')
            last_name = message.get('from', {}).get('last_name', '')
            text = message.get('text', '')
            
            if not chat_id or not text:
                logger.warning(f"Invalid Telegram update: {update_data}")
                return {"success": False, "error": "Invalid update data"}
            
            # Save message to conversation
            await self._save_incoming_message(chat_id, user_id, username, first_name, last_name, text, company_id)
            
            # If AI is enabled, generate response
            if self.ai_settings.get("enabled", False):
                # Get conversation history
                history = await self._get_conversation_history(chat_id, company_id, limit=10)
                
                # Generate AI response
                ai_response = await self._generate_ai_response(text, history)
                
                # Send and save AI response
                result = await self._send_ai_response(chat_id, ai_response, company_id)
                return {"success": True, "response": result}
            
            return {"success": True, "ai_disabled": True}
            
        except Exception as e:
            logger.exception(f"Error processing Telegram update: {e}")
            return {"success": False, "error": str(e)}

    async def _save_incoming_message(self, chat_id: str, user_id: str, 
                                   username: str, first_name: str, last_name: str,
                                   text: str, company_id: str) -> Message:
        """Save incoming message to database"""
        try:
            # Get or create conversation
            company = await sync_to_async(Company.objects.get)(id=company_id)
            
            conversation, created = await sync_to_async(Conversation.objects.get_or_create)(
                external_id=chat_id,
                platform="telegram",
                company=company,
                defaults={
                    "title": f"{first_name} {last_name}".strip() or username or f"Telegram User {user_id}",
                    "created_at": timezone.now(),
                    "updated_at": timezone.now(),
                }
            )
            
            # Create new message
            message = await sync_to_async(Message.objects.create)(
                conversation=conversation,
                sender_id=user_id,
                sender_name=f"{first_name} {last_name}".strip() or username or f"User {user_id}",
                text=text,
                message_type="text",
                direction="incoming",
                status="delivered",
                metadata={"platform": "telegram", "username": username}
            )
            
            # Update conversation last message and time
            conversation.last_message = text
            conversation.updated_at = timezone.now()
            await sync_to_async(conversation.save)()
            
            return message
        except Exception as e:
            logger.exception(f"Error saving incoming Telegram message: {e}")
            raise

    async def _get_conversation_history(self, chat_id: str, company_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get conversation history for AI context"""
        try:
            company = await sync_to_async(Company.objects.get)(id=company_id)
            conversation = await sync_to_async(Conversation.objects.get)(
                external_id=chat_id,
                platform="telegram",
                company=company
            )
            
            messages = await sync_to_async(list)(
                Message.objects.filter(conversation=conversation)
                .order_by('-created_at')[:limit]
                .values('text', 'direction', 'created_at')
            )
            
            # Convert to format expected by AI
            history = []
            for msg in reversed(messages):
                history.append({
                    "text": msg["text"],
                    "isOutgoing": msg["direction"] == "outgoing",
                    "timestamp": msg["created_at"].isoformat()
                })
            
            return history
        except Exception as e:
            logger.exception(f"Error retrieving conversation history: {e}")
            return []

    async def _generate_ai_response(self, message: str, history: List[Dict[str, Any]]) -> str:
        """Generate AI response using OpenAI API"""
        try:
            # Import OpenAI here to avoid dependency issues
            from openai import AsyncOpenAI
            
            if not self.ai_settings.get("api_key"):
                return "Извините, API ключ для AI-ассистента не настроен."
            
            openai_client = AsyncOpenAI(api_key=self.ai_settings.get("api_key"))
            
            # Format history for OpenAI
            formatted_history = [
                {"role": "system", "content": self.ai_settings.get("system_prompt")}
            ]
            
            # Add conversation history
            for msg in history:
                role = "assistant" if msg["isOutgoing"] else "user"
                formatted_history.append({
                    "role": role,
                    "content": msg["text"]
                })
            
            # Add current message
            formatted_history.append({"role": "user", "content": message})
            
            # Generate response
            response = await openai_client.chat.completions.create(
                model=self.ai_settings.get("model"),
                messages=formatted_history,
                temperature=self.ai_settings.get("temperature"),
                max_tokens=self.ai_settings.get("max_tokens")
            )
            
            return response.choices[0].message.content
        except ImportError:
            return "OpenAI API недоступна на сервере."
        except Exception as e:
            logger.exception(f"Error generating AI response: {e}")
            return f"Ошибка генерации ответа: {str(e)}"

    async def _send_ai_response(self, chat_id: str, ai_response: str, company_id: str) -> Dict[str, Any]:
        """Send AI response to user and save to database"""
        try:
            # Send message via Telegram
            result = await sync_to_async(self.telegram_service.send_message)(
                chat_id=chat_id,
                message=ai_response,
                company_id=company_id
            )
            
            # Save message to database
            if result.get("ok", False):
                company = await sync_to_async(Company.objects.get)(id=company_id)
                conversation = await sync_to_async(Conversation.objects.get)(
                    external_id=chat_id,
                    platform="telegram",
                    company=company
                )
                
                await sync_to_async(Message.objects.create)(
                    conversation=conversation,
                    sender_id="bot",
                    sender_name="AI Assistant",
                    text=ai_response,
                    message_type="text",
                    direction="outgoing",
                    status="delivered",
                    metadata={"platform": "telegram", "ai_generated": True}
                )
                
                # Update conversation
                conversation.last_message = ai_response
                conversation.updated_at = timezone.now()
                await sync_to_async(conversation.save)()
            
            return result
        except Exception as e:
            logger.exception(f"Error sending AI response: {e}")
            return {"ok": False, "error": str(e)}
            
    def update_ai_settings(self, settings_data: Dict[str, Any], company_id: Optional[str] = None) -> Dict[str, Any]:
        """Update AI assistant settings"""
        try:
            # Update settings
            for key, value in settings_data.items():
                if key in self.ai_settings:
                    self.ai_settings[key] = value
            
            # In production, save settings to database per company
            # For now, save to JSON file
            with open(settings.BASE_DIR / 'ai_assistant_settings.json', 'w', encoding='utf-8') as f:
                json.dump(self.ai_settings, f, indent=2, ensure_ascii=False)
                
            return {"success": True, "settings": self.ai_settings}
        except Exception as e:
            logger.exception(f"Error updating AI settings: {e}")
            return {"success": False, "error": str(e)}
            
    def get_ai_settings(self, company_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current AI assistant settings"""
        return {"success": True, "settings": self.ai_settings}
