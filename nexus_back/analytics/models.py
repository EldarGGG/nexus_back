from django.db import models
import uuid
from django.contrib.auth import get_user_model

User = get_user_model()

class ConversationMetrics(models.Model):
    """Daily aggregated conversation metrics"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='conversation_metrics')
    date = models.DateField()
    platform = models.CharField(max_length=50)
    total_conversations = models.IntegerField(default=0)
    new_conversations = models.IntegerField(default=0)
    active_conversations = models.IntegerField(default=0)
    closed_conversations = models.IntegerField(default=0)
    avg_response_time = models.DurationField(null=True, blank=True)
    customer_satisfaction_score = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ['company', 'date', 'platform']

    def __str__(self):
        return f"{self.company.name} - {self.date} - {self.platform}"

class MessageMetrics(models.Model):
    """Daily aggregated message metrics"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='message_metrics')
    date = models.DateField()
    platform = models.CharField(max_length=50)
    total_messages = models.IntegerField(default=0)
    incoming_messages = models.IntegerField(default=0)
    outgoing_messages = models.IntegerField(default=0)
    ai_responses = models.IntegerField(default=0)
    human_responses = models.IntegerField(default=0)

    class Meta:
        unique_together = ['company', 'date', 'platform']

    def __str__(self):
        return f"{self.company.name} - {self.date} - {self.platform}"

class AgentPerformance(models.Model):
    """Agent performance metrics"""
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='performance_metrics')
    date = models.DateField()
    conversations_handled = models.IntegerField(default=0)
    messages_sent = models.IntegerField(default=0)
    avg_response_time = models.DurationField(null=True, blank=True)
    customer_rating = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ['agent', 'date']

    def __str__(self):
        return f"{self.agent.email} - {self.date}"
