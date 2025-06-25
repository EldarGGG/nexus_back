"""
AI service for generating automated responses using Google Gemini
"""
import logging
from typing import Dict, Any, List, Optional
from django.conf import settings
try:
    from google import genai
except ImportError:
    genai = None

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered message processing and response generation"""

    def __init__(self):
        self.api_key = getattr(settings, 'GOOGLE_AI_API_KEY', '')
        if self.api_key and genai:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            self.model = None
            logger.warning("Google AI API key not configured or google-genai not installed")

    def generate_response(self, message: str, conversation_history: List[Dict[str, Any]], 
                         company_context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI response for incoming message"""
        try:
            if not self.model:
                return {
                    "response": "AI service not available",
                    "confidence": 0.0,
                    "intent": "unknown",
                    "error": "AI model not configured"
                }

            # Build context for the AI
            context = self._build_context(company_context, conversation_history)
            
            # Create prompt
            prompt = self._create_prompt(context, message, conversation_history)
            
            # Generate response
            response = self.model.generate_content(prompt)
            
            # Parse AI response
            ai_response = self._parse_ai_response(response.text)
            
            logger.info(f"AI response generated for message: {message[:50]}...")
            
            return {
                "response": ai_response.get("response", "I'm sorry, I couldn't understand that."),
                "confidence": ai_response.get("confidence", 0.5),
                "intent": ai_response.get("intent", "unknown"),
                "suggested_actions": ai_response.get("suggested_actions", []),
                "requires_human": ai_response.get("requires_human", False)
            }
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return {
                "response": "I'm sorry, I'm having trouble processing your message right now.",
                "confidence": 0.0,
                "intent": "error",
                "error": str(e)
            }

    def analyze_intent(self, message: str) -> Dict[str, Any]:
        """Analyze the intent of an incoming message"""
        try:
            if not self.model:
                return {"intent": "unknown", "confidence": 0.0}

            prompt = f"""
            Analyze the intent of this customer message and classify it into one of these categories:
            - greeting: Customer is greeting or starting conversation
            - question: Customer is asking a question
            - complaint: Customer has a complaint or issue
            - order_inquiry: Customer asking about an order
            - support_request: Customer needs technical support
            - compliment: Customer giving positive feedback
            - goodbye: Customer ending conversation
            - other: None of the above

            Message: "{message}"

            Respond with JSON format:
            {{
                "intent": "category_name",
                "confidence": 0.95,
                "keywords": ["key", "words", "detected"]
            }}
            """

            response = self.model.generate_content(prompt)
            return self._parse_json_response(response.text)
            
        except Exception as e:
            logger.error(f"Error analyzing intent: {str(e)}")
            return {"intent": "unknown", "confidence": 0.0, "error": str(e)}

    def suggest_responses(self, message: str, intent: str, 
                         company_context: Dict[str, Any]) -> List[str]:
        """Suggest multiple response options for agents"""
        try:
            if not self.model:
                return ["I'll help you with that.", "Let me look into this for you.", "Thank you for contacting us."]

            prompt = f"""
            Based on this customer message with intent "{intent}", suggest 3 different professional response options for a customer service agent.
            
            Customer message: "{message}"
            Company: {company_context.get('name', 'Our Company')}
            Industry: {company_context.get('industry', 'Business')}
            
            Make responses:
            1. Professional and helpful
            2. Appropriate for the detected intent
            3. Personalized to the company context
            
            Return as JSON array of strings:
            ["Response 1", "Response 2", "Response 3"]
            """

            response = self.model.generate_content(prompt)
            suggested_responses = self._parse_json_response(response.text)
            
            if isinstance(suggested_responses, list):
                return suggested_responses
            else:
                return ["I'll help you with that.", "Let me look into this for you.", "Thank you for contacting us."]
                
        except Exception as e:
            logger.error(f"Error suggesting responses: {str(e)}")
            return ["I'll help you with that.", "Let me look into this for you.", "Thank you for contacting us."]

    def extract_entities(self, message: str) -> Dict[str, Any]:
        """Extract entities like names, emails, phone numbers from message"""
        try:
            if not self.model:
                return {"entities": {}}

            prompt = f"""
            Extract entities from this customer message. Look for:
            - person_names: Names of people
            - emails: Email addresses
            - phone_numbers: Phone numbers
            - order_numbers: Order or reference numbers
            - dates: Dates mentioned
            - amounts: Money amounts or quantities
            
            Message: "{message}"
            
            Return as JSON:
            {{
                "entities": {{
                    "person_names": ["John Doe"],
                    "emails": ["john@example.com"],
                    "phone_numbers": ["+1234567890"],
                    "order_numbers": ["ORDER123"],
                    "dates": ["2023-12-25"],
                    "amounts": ["$99.99"]
                }}
            }}
            """

            response = self.model.generate_content(prompt)
            return self._parse_json_response(response.text)
            
        except Exception as e:
            logger.error(f"Error extracting entities: {str(e)}")
            return {"entities": {}}

    def analyze_sentiment(self, message: str) -> Dict[str, Any]:
        """Analyze the sentiment of a customer message"""
        try:
            if not self.model:
                return {"sentiment": "neutral", "confidence": 0.0}

            prompt = f"""
            Analyze the sentiment of this customer message and classify it as:
            - positive: Customer is happy, satisfied, or positive
            - negative: Customer is upset, frustrated, or angry
            - neutral: Customer is neutral or just asking questions
            
            Also identify specific emotions if applicable.
            
            Message: "{message}"
            
            Respond with JSON format:
            {{
                "sentiment": "positive|negative|neutral",
                "confidence": 0.95,
                "emotions": ["happy", "satisfied"] or ["frustrated", "angry"] or []
            }}
            """

            response = self.model.generate_content(prompt)
            return self._parse_json_response(response.text)
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {str(e)}")
            return {"sentiment": "neutral", "confidence": 0.0, "error": str(e)}

    def _build_context(self, company_context: Dict[str, Any], 
                      conversation_history: List[Dict[str, Any]]) -> str:
        """Build context string for AI prompts"""
        context = f"""
        Company Information:
        - Name: {company_context.get('name', 'Unknown')}
        - Industry: {company_context.get('industry', 'Unknown')}
        - Description: {company_context.get('description', 'A business')}
        
        Conversation Guidelines:
        - Be professional and helpful
        - Provide accurate information
        - If you don't know something, suggest escalating to a human agent
        - Keep responses concise but complete
        """
        
        if conversation_history:
            context += "\n\nRecent conversation history:\n"
            for msg in conversation_history[-5:]:  # Last 5 messages
                role = "Customer" if msg.get('direction') == 'incoming' else "Agent"
                context += f"{role}: {msg.get('content', '')}\n"
        
        return context

    def _create_prompt(self, context: str, message: str, 
                      conversation_history: List[Dict[str, Any]]) -> str:
        """Create prompt for AI response generation"""
        return f"""
        {context}
        
        Current customer message: "{message}"
        
        Generate an appropriate response as a customer service representative. 
        Consider the conversation history and company context.
        
        Respond with JSON format:
        {{
            "response": "Your helpful response here",
            "confidence": 0.95,
            "intent": "detected_intent",
            "suggested_actions": ["action1", "action2"],
            "requires_human": false
        }}
        """

    def _parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """Parse AI response text into structured data"""
        try:
            import json
            # Try to extract JSON from response
            if '{' in response_text and '}' in response_text:
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                json_str = response_text[start:end]
                return json.loads(json_str)
            else:
                # Fallback to treating entire response as message
                return {
                    "response": response_text.strip(),
                    "confidence": 0.7,
                    "intent": "unknown"
                }
        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}")
            return {
                "response": "I'm here to help. Could you please provide more details?",
                "confidence": 0.5,
                "intent": "unknown"
            }

    def _parse_json_response(self, response_text: str) -> Any:
        """Parse JSON response from AI"""
        try:
            import json
            if '{' in response_text or '[' in response_text:
                # Find JSON in response
                start_brace = response_text.find('{')
                start_bracket = response_text.find('[')
                
                if start_brace == -1:
                    start = start_bracket
                    end = response_text.rfind(']') + 1
                elif start_bracket == -1:
                    start = start_brace
                    end = response_text.rfind('}') + 1
                else:
                    start = min(start_brace, start_bracket)
                    if start == start_brace:
                        end = response_text.rfind('}') + 1
                    else:
                        end = response_text.rfind(']') + 1
                
                json_str = response_text[start:end]
                return json.loads(json_str)
            
            return response_text.strip()
            
        except Exception as e:
            logger.error(f"Error parsing JSON response: {str(e)}")
            return {}

    def is_available(self) -> bool:
        """Check if AI service is available"""
        return self.model is not None and self.api_key != ''

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the AI model"""
        return {
            "model_name": "gemini-pro",
            "provider": "Google AI",
            "available": self.is_available(),
            "features": [
                "Response generation",
                "Intent analysis", 
                "Entity extraction",
                "Response suggestions"
            ]
        }
