from google import genai
from django.conf import settings
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.api_key = getattr(settings, 'GEMINI_API_KEY', '')
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("Gemini API key not configured")
    
    def generate_response_sync(self, message: str, context: Dict, config) -> Optional[Dict]:
        """Synchronous version of generate_response for compatibility"""
        return self.generate_response(message, context, config)
    
    def generate_response(self, message: str, context: Dict, config) -> Optional[Dict]:
        """Generate AI response for customer message"""
        try:
            if not self.client:
                return None
                
            # Build conversation history
            conversation_text = self.build_conversation_context(context)
            
            # Create system prompt
            system_instruction = f"""
            You are a helpful customer service assistant for {context.get('company', 'the company')}.
            You are responding to messages from {context.get('customer_name', 'a customer')} via {context.get('platform', 'messaging')}.
            
            {getattr(config, 'system_prompt', 'Provide helpful customer service.')}
            
            Previous conversation:
            {conversation_text}
            
            Response guidelines:
            - Be concise but helpful
            - Use the customer's name when appropriate
            - Stay professional and friendly
            - If unsure, suggest human assistance
            """
            
            # Generate response using new API
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-001',
                contents=f"Current message from customer: {message}",
                config={
                    'system_instruction': system_instruction,
                    'max_output_tokens': 1000,
                    'temperature': 0.7,
                }
            )
            
            if response.text:
                # Calculate confidence (simplified)
                confidence = self.calculate_confidence(message, response.text)
                
                return {
                    'content': response.text,
                    'confidence': confidence,
                    'model': 'gemini-2.0-flash-001'
                }
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return None
    
    def build_conversation_context(self, context: Dict) -> str:
        """Build conversation context from recent messages"""
        conversation_lines = []
        
        for msg in context.get('recent_messages', []):
            direction_prefix = "Customer" if msg['direction'] == 'inbound' else "Agent"
            conversation_lines.append(f"{direction_prefix}: {msg['content']}")
        
        return "\n".join(conversation_lines[-5:])  # Last 5 messages
    
    def calculate_confidence(self, message: str, response: str) -> float:
        """Calculate confidence score for AI response"""
        # Simplified confidence calculation
        # In production, you'd use more sophisticated methods
        
        # Lower confidence for very short responses
        if len(response.split()) < 3:
            return 0.3
        
        # Lower confidence for generic responses
        generic_phrases = ['i can help', 'let me assist', 'please contact']
        if any(phrase in response.lower() for phrase in generic_phrases):
            return 0.6
        
        # Higher confidence for specific, detailed responses
        if len(response.split()) > 10:
            return 0.9
        
        return 0.7

# Create instance of AIService to be imported in other modules
ai_service = AIService()
