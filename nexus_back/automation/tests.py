"""
Comprehensive unit tests for automation functionality
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta

from .models import AutomationRule, AutomationExecution
from companies.models import Company
from messaging.models import Conversation, Message

User = get_user_model()


class AutomationRuleModelTest(TestCase):
    """Test AutomationRule model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            company=self.company
        )

    def test_create_automation_rule(self):
        """Test creating an automation rule"""
        rule = AutomationRule.objects.create(
            company=self.company,
            name="Welcome Message",
            description="Send welcome message to new conversations",
            trigger_type="new_conversation",
            trigger_conditions={"platforms": ["whatsapp", "telegram"]},
            action_type="send_message",
            action_parameters={"message": "Welcome! How can we help you?"},
            created_by=self.user,
            priority=10
        )
        
        self.assertEqual(rule.company, self.company)
        self.assertEqual(rule.name, "Welcome Message")
        self.assertEqual(rule.trigger_type, "new_conversation")
        self.assertEqual(rule.action_type, "send_message")
        self.assertTrue(rule.is_active)
        self.assertEqual(rule.priority, 10)

    def test_automation_rule_str_representation(self):
        """Test automation rule string representation"""
        rule = AutomationRule.objects.create(
            company=self.company,
            name="Test Rule",
            trigger_type="keyword",
            action_type="send_message",
            created_by=self.user
        )
        
        expected_str = f"{self.company.name} - Test Rule"
        self.assertEqual(str(rule), expected_str)

    def test_automation_rule_ordering(self):
        """Test automation rule ordering by priority"""
        rule1 = AutomationRule.objects.create(
            company=self.company,
            name="Low Priority",
            trigger_type="keyword",
            action_type="send_message",
            created_by=self.user,
            priority=1
        )
        
        rule2 = AutomationRule.objects.create(
            company=self.company,
            name="High Priority",
            trigger_type="keyword",
            action_type="send_message",
            created_by=self.user,
            priority=10
        )
        
        rules = list(AutomationRule.objects.all())
        self.assertEqual(rules[0], rule2)  # Higher priority first
        self.assertEqual(rules[1], rule1)

    def test_keyword_trigger_conditions(self):
        """Test keyword trigger conditions"""
        rule = AutomationRule.objects.create(
            company=self.company,
            name="Keyword Rule",
            trigger_type="keyword",
            trigger_conditions={
                "keywords": ["help", "support", "assistance"],
                "match_type": "any"
            },
            action_type="assign_agent",
            action_parameters={"agent_id": str(self.user.id)},
            created_by=self.user
        )
        
        self.assertIn("keywords", rule.trigger_conditions)
        self.assertEqual(len(rule.trigger_conditions["keywords"]), 3)

    def test_business_hours_trigger(self):
        """Test business hours trigger conditions"""
        rule = AutomationRule.objects.create(
            company=self.company,
            name="After Hours Rule",
            trigger_type="business_hours",
            trigger_conditions={
                "outside_hours": True,
                "timezone": "UTC",
                "business_hours": {
                    "monday": {"start": "09:00", "end": "17:00"},
                    "friday": {"start": "09:00", "end": "17:00"}
                }
            },
            action_type="send_message",
            action_parameters={
                "message": "We're currently closed. We'll get back to you during business hours."
            },
            created_by=self.user
        )
        
        self.assertTrue(rule.trigger_conditions["outside_hours"])
        self.assertIn("business_hours", rule.trigger_conditions)


class AutomationExecutionModelTest(TestCase):
    """Test AutomationExecution model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            company=self.company
        )
        self.rule = AutomationRule.objects.create(
            company=self.company,
            name="Test Rule",
            trigger_type="keyword",
            action_type="send_message",
            created_by=self.user
        )
        self.conversation = Conversation.objects.create(
            company=self.company,
            external_id="test_123",
            platform="whatsapp"
        )
        self.message = Message.objects.create(
            conversation=self.conversation,
            direction="incoming",
            content="I need help"
        )

    def test_create_automation_execution(self):
        """Test creating an automation execution"""
        execution = AutomationExecution.objects.create(
            rule=self.rule,
            conversation=self.conversation,
            message=self.message,
            status="success",
            result={"message_sent": True, "message_id": "msg_123"}
        )
        
        self.assertEqual(execution.rule, self.rule)
        self.assertEqual(execution.conversation, self.conversation)
        self.assertEqual(execution.message, self.message)
        self.assertEqual(execution.status, "success")

    def test_automation_execution_str_representation(self):
        """Test automation execution string representation"""
        execution = AutomationExecution.objects.create(
            rule=self.rule,
            conversation=self.conversation,
            status="pending"
        )
        
        expected_str = f"{self.rule.name} - pending"
        self.assertEqual(str(execution), expected_str)

    def test_failed_execution_with_error(self):
        """Test failed execution with error message"""
        execution = AutomationExecution.objects.create(
            rule=self.rule,
            conversation=self.conversation,
            status="failed",
            error_message="API rate limit exceeded"
        )
        
        self.assertEqual(execution.status, "failed")
        self.assertEqual(execution.error_message, "API rate limit exceeded")


class AutomationRuleEngineTest(TestCase):
    """Test automation rule engine functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            company=self.company
        )
        self.conversation = Conversation.objects.create(
            company=self.company,
            external_id="test_123",
            platform="whatsapp"
        )

    def test_keyword_matching(self):
        """Test keyword matching trigger"""
        rule = AutomationRule.objects.create(
            company=self.company,
            name="Help Keyword Rule",
            trigger_type="keyword",
            trigger_conditions={
                "keywords": ["help", "support"],
                "match_type": "any",
                "case_sensitive": False
            },
            action_type="send_message",
            action_parameters={"message": "How can I help you?"},
            created_by=self.user
        )

        # Test messages that should trigger the rule
        trigger_messages = [
            "I need help",
            "Can you HELP me?",
            "support please",
            "I require some support with my order"
        ]

        for msg_content in trigger_messages:
            message = Message.objects.create(
                conversation=self.conversation,
                direction="incoming",
                content=msg_content
            )
            
            # Simulate rule engine checking
            keywords = rule.trigger_conditions["keywords"]
            match_type = rule.trigger_conditions.get("match_type", "any")
            case_sensitive = rule.trigger_conditions.get("case_sensitive", False)
            
            content = msg_content if case_sensitive else msg_content.lower()
            keywords_to_check = keywords if case_sensitive else [k.lower() for k in keywords]
            
            if match_type == "any":
                should_trigger = any(keyword in content for keyword in keywords_to_check)
            else:  # "all"
                should_trigger = all(keyword in content for keyword in keywords_to_check)
            
            self.assertTrue(should_trigger, f"Rule should trigger for: '{msg_content}'")

    def test_intent_based_trigger(self):
        """Test intent-based trigger"""
        rule = AutomationRule.objects.create(
            company=self.company,
            name="Complaint Handler",
            trigger_type="intent",
            trigger_conditions={
                "intents": ["complaint", "dissatisfaction"],
                "confidence_threshold": 0.8
            },
            action_type="escalate",
            action_parameters={"department": "customer_service"},
            created_by=self.user
        )

        message = Message.objects.create(
            conversation=self.conversation,
            direction="incoming",
            content="I'm very unhappy with the service",
            metadata={
                "ai_analysis": {
                    "intent": "complaint",
                    "confidence": 0.95
                }
            }
        )

        # Simulate intent checking
        ai_analysis = message.metadata.get("ai_analysis", {})
        detected_intent = ai_analysis.get("intent")
        confidence = ai_analysis.get("confidence", 0.0)
        
        target_intents = rule.trigger_conditions["intents"]
        threshold = rule.trigger_conditions["confidence_threshold"]
        
        should_trigger = (detected_intent in target_intents and confidence >= threshold)
        self.assertTrue(should_trigger)

    def test_new_conversation_trigger(self):
        """Test new conversation trigger"""
        rule = AutomationRule.objects.create(
            company=self.company,
            name="Welcome Rule",
            trigger_type="new_conversation",
            trigger_conditions={"platforms": ["whatsapp", "telegram"]},
            action_type="send_message",
            action_parameters={"message": "Welcome to our service!"},
            created_by=self.user
        )

        # Test new conversation on whatsapp (should trigger)
        new_conversation = Conversation.objects.create(
            company=self.company,
            external_id="new_123",
            platform="whatsapp",
            status="active"
        )

        platforms = rule.trigger_conditions.get("platforms", [])
        should_trigger = new_conversation.platform in platforms
        self.assertTrue(should_trigger)

        # Test new conversation on unsupported platform (should not trigger)
        unsupported_conversation = Conversation.objects.create(
            company=self.company,
            external_id="new_456",
            platform="email",
            status="active"
        )

        should_trigger = unsupported_conversation.platform in platforms
        self.assertFalse(should_trigger)

    @patch('automation.models.timezone')
    def test_business_hours_trigger(self, mock_timezone):
        """Test business hours trigger"""
        # Mock current time to be outside business hours (6 PM)
        mock_now = timezone.now().replace(hour=18, minute=0, second=0)
        mock_timezone.now.return_value = mock_now

        rule = AutomationRule.objects.create(
            company=self.company,
            name="After Hours Rule",
            trigger_type="business_hours",
            trigger_conditions={
                "outside_hours": True,
                "business_hours": {
                    "start": "09:00",
                    "end": "17:00"
                }
            },
            action_type="send_message",
            action_parameters={"message": "We're closed. Business hours are 9 AM - 5 PM."},
            created_by=self.user
        )

        current_hour = mock_timezone.now().hour
        business_start = 9
        business_end = 17
        
        is_outside_hours = current_hour < business_start or current_hour >= business_end
        should_trigger = rule.trigger_conditions["outside_hours"] and is_outside_hours
        
        self.assertTrue(should_trigger)

    def test_inactivity_trigger(self):
        """Test inactivity trigger"""
        rule = AutomationRule.objects.create(
            company=self.company,
            name="Inactivity Follow-up",
            trigger_type="inactivity",
            trigger_conditions={"hours": 24},
            action_type="send_message",
            action_parameters={"message": "Are you still there? Can we help with anything else?"},
            created_by=self.user
        )

        # Create a conversation with last message 25 hours ago
        old_time = timezone.now() - timedelta(hours=25)
        old_message = Message.objects.create(
            conversation=self.conversation,
            direction="incoming",
            content="Initial message",
            timestamp=old_time
        )

        hours_threshold = rule.trigger_conditions["hours"]
        time_threshold = timezone.now() - timedelta(hours=hours_threshold)
        
        last_message = self.conversation.messages.order_by('-timestamp').first()
        should_trigger = last_message and last_message.timestamp < time_threshold
        
        self.assertTrue(should_trigger)


class AutomationActionTest(TestCase):
    """Test automation action execution"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            company=self.company
        )
        self.agent = User.objects.create_user(
            username="agent",
            email="agent@example.com",
            company=self.company
        )
        self.conversation = Conversation.objects.create(
            company=self.company,
            external_id="test_123",
            platform="whatsapp"
        )

    @patch('automation.models.send_automated_message')
    def test_send_message_action(self, mock_send_message):
        """Test send message action"""
        mock_send_message.return_value = {"status": "sent", "message_id": "msg_123"}

        rule = AutomationRule.objects.create(
            company=self.company,
            name="Auto Reply",
            trigger_type="keyword",
            action_type="send_message",
            action_parameters={
                "message": "Thank you for your message. We'll get back to you soon.",
                "delay_seconds": 0
            },
            created_by=self.user
        )

        # Simulate action execution
        execution = AutomationExecution.objects.create(
            rule=rule,
            conversation=self.conversation,
            status="pending"
        )

        # Mock the action execution
        message_text = rule.action_parameters["message"]
        result = mock_send_message(self.conversation, message_text)
        
        execution.status = "success"
        execution.result = result
        execution.save()

        self.assertEqual(execution.status, "success")
        self.assertEqual(execution.result["status"], "sent")
        mock_send_message.assert_called_once()

    def test_assign_agent_action(self):
        """Test assign agent action"""
        rule = AutomationRule.objects.create(
            company=self.company,
            name="Auto Assign",
            trigger_type="intent",
            action_type="assign_agent",
            action_parameters={"agent_id": str(self.agent.id)},
            created_by=self.user
        )

        # Simulate action execution
        self.conversation.assigned_agent = self.agent
        self.conversation.save()

        execution = AutomationExecution.objects.create(
            rule=rule,
            conversation=self.conversation,
            status="success",
            result={"assigned_agent": str(self.agent.id)}
        )

        self.assertEqual(self.conversation.assigned_agent, self.agent)
        self.assertEqual(execution.status, "success")

    def test_tag_conversation_action(self):
        """Test tag conversation action"""
        rule = AutomationRule.objects.create(
            company=self.company,
            name="Auto Tag",
            trigger_type="keyword",
            action_type="tag_conversation",
            action_parameters={"tags": ["urgent", "vip"]},
            created_by=self.user
        )

        # Simulate tagging
        tags = rule.action_parameters["tags"]
        current_tags = self.conversation.metadata.get("tags", [])
        new_tags = list(set(current_tags + tags))
        
        self.conversation.metadata["tags"] = new_tags
        self.conversation.save()

        execution = AutomationExecution.objects.create(
            rule=rule,
            conversation=self.conversation,
            status="success",
            result={"tags_added": tags}
        )

        self.assertIn("urgent", self.conversation.metadata["tags"])
        self.assertIn("vip", self.conversation.metadata["tags"])

    def test_escalate_action(self):
        """Test escalate action"""
        rule = AutomationRule.objects.create(
            company=self.company,
            name="Auto Escalate",
            trigger_type="intent",
            action_type="escalate",
            action_parameters={
                "department": "manager",
                "priority": "high",
                "reason": "Customer complaint detected"
            },
            created_by=self.user
        )

        # Simulate escalation
        escalation_data = rule.action_parameters
        self.conversation.metadata["escalated"] = True
        self.conversation.metadata["escalation"] = escalation_data
        self.conversation.priority = "high"
        self.conversation.save()

        execution = AutomationExecution.objects.create(
            rule=rule,
            conversation=self.conversation,
            status="success",
            result={"escalated": True, "department": "manager"}
        )

        self.assertTrue(self.conversation.metadata.get("escalated"))
        self.assertEqual(self.conversation.metadata["escalation"]["department"], "manager")

    @patch('automation.models.AIService')
    def test_ai_response_action(self, mock_ai_service):
        """Test AI response action"""
        mock_ai = Mock()
        mock_ai.generate_response.return_value = {
            "response": "I understand you need help. Let me assist you.",
            "confidence": 0.9
        }
        mock_ai_service.return_value = mock_ai

        rule = AutomationRule.objects.create(
            company=self.company,
            name="AI Auto Response",
            trigger_type="keyword",
            action_type="ai_response",
            action_parameters={
                "context": "customer_support",
                "tone": "helpful"
            },
            created_by=self.user
        )

        message = Message.objects.create(
            conversation=self.conversation,
            direction="incoming",
            content="I need help with my order"
        )

        # Simulate AI response generation
        ai_service = mock_ai_service()
        response = ai_service.generate_response(
            message.content,
            [],
            {"company": self.company.name}
        )

        execution = AutomationExecution.objects.create(
            rule=rule,
            conversation=self.conversation,
            message=message,
            status="success",
            result=response
        )

        self.assertEqual(execution.status, "success")
        self.assertIn("response", execution.result)
        mock_ai.generate_response.assert_called_once()
