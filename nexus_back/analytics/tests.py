"""
Comprehensive unit tests for analytics functionality
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta, date
from unittest.mock import patch, Mock

from .models import ConversationMetrics, MessageMetrics, AgentPerformance
from companies.models import Company
from messaging.models import Conversation, Message

User = get_user_model()


class ConversationMetricsModelTest(TestCase):
    """Test ConversationMetrics model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.today = date.today()

    def test_create_conversation_metrics(self):
        """Test creating conversation metrics"""
        metrics = ConversationMetrics.objects.create(
            company=self.company,
            date=self.today,
            platform="whatsapp",
            total_conversations=100,
            new_conversations=25,
            active_conversations=75,
            closed_conversations=20,
            avg_response_time=timedelta(minutes=15),
            customer_satisfaction_score=4.2
        )
        
        self.assertEqual(metrics.company, self.company)
        self.assertEqual(metrics.platform, "whatsapp")
        self.assertEqual(metrics.total_conversations, 100)
        self.assertEqual(metrics.new_conversations, 25)
        self.assertEqual(metrics.avg_response_time, timedelta(minutes=15))
        self.assertEqual(metrics.customer_satisfaction_score, 4.2)

    def test_conversation_metrics_str_representation(self):
        """Test conversation metrics string representation"""
        metrics = ConversationMetrics.objects.create(
            company=self.company,
            date=self.today,
            platform="telegram",
            total_conversations=50
        )
        
        expected_str = f"{self.company.name} - {self.today} - telegram"
        self.assertEqual(str(metrics), expected_str)

    def test_unique_constraint(self):
        """Test unique constraint on company, date, platform"""
        ConversationMetrics.objects.create(
            company=self.company,
            date=self.today,
            platform="whatsapp",
            total_conversations=100
        )
        
        # Creating another metric with same company, date, platform should raise error
        with self.assertRaises(Exception):
            ConversationMetrics.objects.create(
                company=self.company,
                date=self.today,
                platform="whatsapp",
                total_conversations=200
            )

    def test_metrics_calculation(self):
        """Test metrics calculation logic"""
        # Create conversations for testing
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # New conversations
        for i in range(5):
            Conversation.objects.create(
                company=self.company,
                external_id=f"new_{i}",
                platform="whatsapp",
                created_at=timezone.now() - timedelta(hours=i)
            )
        
        # Existing conversations
        for i in range(3):
            Conversation.objects.create(
                company=self.company,
                external_id=f"old_{i}",
                platform="whatsapp",
                created_at=timezone.now() - timedelta(days=2),
                updated_at=timezone.now() - timedelta(hours=i)
            )
        
        # Count today's conversations
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        total_conversations = Conversation.objects.filter(
            company=self.company,
            platform="whatsapp",
            updated_at__gte=today_start,
            updated_at__lt=today_end
        ).count()
        
        new_conversations = Conversation.objects.filter(
            company=self.company,
            platform="whatsapp",
            created_at__gte=today_start,
            created_at__lt=today_end
        ).count()
        
        self.assertEqual(new_conversations, 5)
        self.assertGreaterEqual(total_conversations, 5)


class MessageMetricsModelTest(TestCase):
    """Test MessageMetrics model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.today = date.today()

    def test_create_message_metrics(self):
        """Test creating message metrics"""
        metrics = MessageMetrics.objects.create(
            company=self.company,
            date=self.today,
            platform="whatsapp",
            total_messages=500,
            incoming_messages=300,
            outgoing_messages=200,
            ai_responses=150,
            human_responses=50
        )
        
        self.assertEqual(metrics.company, self.company)
        self.assertEqual(metrics.total_messages, 500)
        self.assertEqual(metrics.incoming_messages, 300)
        self.assertEqual(metrics.outgoing_messages, 200)
        self.assertEqual(metrics.ai_responses, 150)
        self.assertEqual(metrics.human_responses, 50)

    def test_message_metrics_str_representation(self):
        """Test message metrics string representation"""
        metrics = MessageMetrics.objects.create(
            company=self.company,
            date=self.today,
            platform="instagram",
            total_messages=100
        )
        
        expected_str = f"{self.company.name} - {self.today} - instagram"
        self.assertEqual(str(metrics), expected_str)

    def test_message_metrics_unique_constraint(self):
        """Test unique constraint on company, date, platform"""
        MessageMetrics.objects.create(
            company=self.company,
            date=self.today,
            platform="telegram",
            total_messages=100
        )
        
        with self.assertRaises(Exception):
            MessageMetrics.objects.create(
                company=self.company,
                date=self.today,
                platform="telegram",
                total_messages=200
            )

    def test_message_metrics_calculation(self):
        """Test message metrics calculation"""
        # Create a conversation
        conversation = Conversation.objects.create(
            company=self.company,
            external_id="test_conv",
            platform="whatsapp"
        )
        
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Create messages for today
        incoming_messages = []
        outgoing_messages = []
        
        for i in range(10):
            # Incoming messages
            msg = Message.objects.create(
                conversation=conversation,
                direction="incoming",
                content=f"Incoming message {i}",
                timestamp=today_start + timedelta(hours=i)
            )
            incoming_messages.append(msg)
            
            # Outgoing messages (some AI, some human)
            msg = Message.objects.create(
                conversation=conversation,
                direction="outgoing",
                content=f"Outgoing message {i}",
                timestamp=today_start + timedelta(hours=i, minutes=30),
                metadata={"is_ai_generated": i % 2 == 0}  # Every other message is AI
            )
            outgoing_messages.append(msg)
        
        # Calculate metrics
        today_end = today_start + timedelta(days=1)
        
        total_messages = Message.objects.filter(
            conversation__company=self.company,
            conversation__platform="whatsapp",
            timestamp__gte=today_start,
            timestamp__lt=today_end
        ).count()
        
        incoming_count = Message.objects.filter(
            conversation__company=self.company,
            conversation__platform="whatsapp",
            direction="incoming",
            timestamp__gte=today_start,
            timestamp__lt=today_end
        ).count()
        
        outgoing_count = Message.objects.filter(
            conversation__company=self.company,
            conversation__platform="whatsapp",
            direction="outgoing",
            timestamp__gte=today_start,
            timestamp__lt=today_end
        ).count()
        
        ai_responses = Message.objects.filter(
            conversation__company=self.company,
            conversation__platform="whatsapp",
            direction="outgoing",
            metadata__is_ai_generated=True,
            timestamp__gte=today_start,
            timestamp__lt=today_end
        ).count()
        
        self.assertEqual(total_messages, 20)
        self.assertEqual(incoming_count, 10)
        self.assertEqual(outgoing_count, 10)
        self.assertEqual(ai_responses, 5)


class AgentPerformanceModelTest(TestCase):
    """Test AgentPerformance model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.agent = User.objects.create_user(
            username="agent",
            email="agent@example.com",
            company=self.company
        )
        self.today = date.today()

    def test_create_agent_performance(self):
        """Test creating agent performance record"""
        performance = AgentPerformance.objects.create(
            agent=self.agent,
            date=self.today,
            conversations_handled=15,
            messages_sent=50,
            avg_response_time=timedelta(minutes=8),
            customer_rating=4.5
        )
        
        self.assertEqual(performance.agent, self.agent)
        self.assertEqual(performance.conversations_handled, 15)
        self.assertEqual(performance.messages_sent, 50)
        self.assertEqual(performance.avg_response_time, timedelta(minutes=8))
        self.assertEqual(performance.customer_rating, 4.5)

    def test_agent_performance_str_representation(self):
        """Test agent performance string representation"""
        performance = AgentPerformance.objects.create(
            agent=self.agent,
            date=self.today,
            conversations_handled=10
        )
        
        expected_str = f"{self.agent.email} - {self.today}"
        self.assertEqual(str(performance), expected_str)

    def test_agent_performance_unique_constraint(self):
        """Test unique constraint on agent and date"""
        AgentPerformance.objects.create(
            agent=self.agent,
            date=self.today,
            conversations_handled=10
        )
        
        with self.assertRaises(Exception):
            AgentPerformance.objects.create(
                agent=self.agent,
                date=self.today,
                conversations_handled=20
            )

    def test_agent_performance_calculation(self):
        """Test agent performance calculation"""
        # Create conversations assigned to the agent
        conversations = []
        for i in range(5):
            conv = Conversation.objects.create(
                company=self.company,
                external_id=f"conv_{i}",
                platform="whatsapp",
                assigned_agent=self.agent,
                created_at=timezone.now() - timedelta(hours=i)
            )
            conversations.append(conv)
        
        # Create messages sent by the agent
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        messages_sent = 0
        
        for conv in conversations:
            for j in range(3):  # 3 messages per conversation
                Message.objects.create(
                    conversation=conv,
                    direction="outgoing",
                    content=f"Response {j}",
                    timestamp=today_start + timedelta(hours=j),
                    sender_info={"agent_id": str(self.agent.id)}
                )
                messages_sent += 1
        
        # Calculate performance metrics
        today_end = today_start + timedelta(days=1)
        
        conversations_handled = Conversation.objects.filter(
            assigned_agent=self.agent,
            updated_at__gte=today_start,
            updated_at__lt=today_end
        ).count()
        
        agent_messages = Message.objects.filter(
            conversation__assigned_agent=self.agent,
            direction="outgoing",
            timestamp__gte=today_start,
            timestamp__lt=today_end,
            sender_info__agent_id=str(self.agent.id)
        ).count()
        
        self.assertEqual(conversations_handled, 5)
        self.assertEqual(agent_messages, 15)


class AnalyticsServiceTest(TestCase):
    """Test analytics service functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.agent = User.objects.create_user(
            username="agent",
            email="agent@example.com",
            company=self.company
        )

    def test_daily_metrics_aggregation(self):
        """Test daily metrics aggregation"""
        # Create test data for today
        today = timezone.now().date()
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Create conversations
        conversations = []
        for i in range(3):
            conv = Conversation.objects.create(
                company=self.company,
                external_id=f"daily_conv_{i}",
                platform="whatsapp",
                created_at=today_start + timedelta(hours=i)
            )
            conversations.append(conv)
        
        # Create messages
        for conv in conversations:
            # Incoming message
            Message.objects.create(
                conversation=conv,
                direction="incoming",
                content="Customer message",
                timestamp=today_start + timedelta(hours=1)
            )
            
            # Outgoing AI response
            Message.objects.create(
                conversation=conv,
                direction="outgoing",
                content="AI response",
                timestamp=today_start + timedelta(hours=1, minutes=5),
                metadata={"is_ai_generated": True}
            )
            
            # Human response
            Message.objects.create(
                conversation=conv,
                direction="outgoing",
                content="Human response",
                timestamp=today_start + timedelta(hours=1, minutes=10),
                sender_info={"agent_id": str(self.agent.id)}
            )
        
        # Aggregate metrics
        total_conversations = Conversation.objects.filter(
            company=self.company,
            platform="whatsapp",
            created_at__date=today
        ).count()
        
        total_messages = Message.objects.filter(
            conversation__company=self.company,
            conversation__platform="whatsapp",
            timestamp__date=today
        ).count()
        
        incoming_messages = Message.objects.filter(
            conversation__company=self.company,
            conversation__platform="whatsapp",
            direction="incoming",
            timestamp__date=today
        ).count()
        
        ai_responses = Message.objects.filter(
            conversation__company=self.company,
            conversation__platform="whatsapp",
            direction="outgoing",
            metadata__is_ai_generated=True,
            timestamp__date=today
        ).count()
        
        self.assertEqual(total_conversations, 3)
        self.assertEqual(total_messages, 9)  # 3 conversations × 3 messages each
        self.assertEqual(incoming_messages, 3)
        self.assertEqual(ai_responses, 3)

    def test_response_time_calculation(self):
        """Test response time calculation"""
        conversation = Conversation.objects.create(
            company=self.company,
            external_id="response_time_test",
            platform="whatsapp"
        )
        
        base_time = timezone.now()
        
        # Customer message
        customer_msg = Message.objects.create(
            conversation=conversation,
            direction="incoming",
            content="I need help",
            timestamp=base_time
        )
        
        # Agent response after 5 minutes
        agent_response = Message.objects.create(
            conversation=conversation,
            direction="outgoing",
            content="How can I help you?",
            timestamp=base_time + timedelta(minutes=5),
            sender_info={"agent_id": str(self.agent.id)}
        )
        
        # Calculate response time
        response_time = agent_response.timestamp - customer_msg.timestamp
        expected_response_time = timedelta(minutes=5)
        
        self.assertEqual(response_time, expected_response_time)

    def test_platform_breakdown(self):
        """Test metrics breakdown by platform"""
        platforms = ["whatsapp", "telegram", "instagram"]
        
        for platform in platforms:
            # Create conversations for each platform
            for i in range(2):
                conv = Conversation.objects.create(
                    company=self.company,
                    external_id=f"{platform}_conv_{i}",
                    platform=platform
                )
                
                # Create messages
                Message.objects.create(
                    conversation=conv,
                    direction="incoming",
                    content="Customer message"
                )
                
                Message.objects.create(
                    conversation=conv,
                    direction="outgoing",
                    content="Response"
                )
        
        # Count by platform
        for platform in platforms:
            conv_count = Conversation.objects.filter(
                company=self.company,
                platform=platform
            ).count()
            
            msg_count = Message.objects.filter(
                conversation__company=self.company,
                conversation__platform=platform
            ).count()
            
            self.assertEqual(conv_count, 2)
            self.assertEqual(msg_count, 4)  # 2 conversations × 2 messages each

    @patch('analytics.models.timezone')
    def test_metrics_for_different_time_periods(self, mock_timezone):
        """Test metrics calculation for different time periods"""
        base_time = timezone.now()
        mock_timezone.now.return_value = base_time
        
        # Create data for last 7 days
        for day_offset in range(7):
            day_time = base_time - timedelta(days=day_offset)
            
            conv = Conversation.objects.create(
                company=self.company,
                external_id=f"conv_day_{day_offset}",
                platform="whatsapp",
                created_at=day_time
            )
            
            Message.objects.create(
                conversation=conv,
                direction="incoming",
                content="Daily message",
                timestamp=day_time
            )
        
        # Calculate weekly metrics
        week_start = base_time - timedelta(days=7)
        weekly_conversations = Conversation.objects.filter(
            company=self.company,
            created_at__gte=week_start
        ).count()
        
        weekly_messages = Message.objects.filter(
            conversation__company=self.company,
            timestamp__gte=week_start
        ).count()
        
        self.assertEqual(weekly_conversations, 7)
        self.assertEqual(weekly_messages, 7)

    def test_customer_satisfaction_tracking(self):
        """Test customer satisfaction score tracking"""
        conversation = Conversation.objects.create(
            company=self.company,
            external_id="satisfaction_test",
            platform="whatsapp"
        )
        
        # Add satisfaction rating to conversation metadata
        conversation.metadata = {
            "satisfaction_rating": 4.5,
            "feedback": "Great service!"
        }
        conversation.save()
        
        # Calculate average satisfaction
        conversations_with_ratings = Conversation.objects.filter(
            company=self.company,
            metadata__satisfaction_rating__isnull=False
        )
        
        if conversations_with_ratings.exists():
            total_rating = sum(
                float(conv.metadata.get("satisfaction_rating", 0))
                for conv in conversations_with_ratings
            )
            avg_rating = total_rating / conversations_with_ratings.count()
            
            self.assertEqual(avg_rating, 4.5)

    def test_agent_workload_distribution(self):
        """Test agent workload distribution tracking"""
        # Create multiple agents
        agents = []
        for i in range(3):
            agent = User.objects.create_user(
                username=f"agent_{i}",
                email=f"agent_{i}@example.com",
                company=self.company
            )
            agents.append(agent)
        
        # Assign different workloads
        workloads = [5, 3, 7]  # conversations per agent
        
        for agent, workload in zip(agents, workloads):
            for i in range(workload):
                Conversation.objects.create(
                    company=self.company,
                    external_id=f"{agent.username}_conv_{i}",
                    platform="whatsapp",
                    assigned_agent=agent
                )
        
        # Check workload distribution
        for agent, expected_workload in zip(agents, workloads):
            actual_workload = Conversation.objects.filter(
                company=self.company,
                assigned_agent=agent
            ).count()
            
            self.assertEqual(actual_workload, expected_workload)
