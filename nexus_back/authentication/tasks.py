from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import UserSession, CustomUser
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def cleanup_old_sessions():
    """Clean up old user sessions"""
    try:
        # Remove sessions older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        old_sessions = UserSession.objects.filter(created_at__lt=cutoff_date)
        
        count = old_sessions.count()
        old_sessions.delete()
        
        logger.info(f"Cleaned up {count} old sessions")
        return f"Cleaned up {count} old sessions"
        
    except Exception as e:
        logger.error(f"Error cleaning up old sessions: {str(e)}")
        raise


@shared_task
def send_password_reset_email(user_id, reset_token):
    """Send password reset email"""
    try:
        user = CustomUser.objects.get(id=user_id)
        
        subject = "Password Reset Request"
        message = f"""
        Hello {user.first_name or user.email},
        
        You requested a password reset for your Nexus account.
        
        Click the link below to reset your password:
        {settings.FRONTEND_URL}/reset-password/{reset_token}
        
        This link will expire in 1 hour.
        
        If you didn't request this, please ignore this email.
        
        Best regards,
        The Nexus Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        logger.info(f"Password reset email sent to {user.email}")
        return f"Password reset email sent to {user.email}"
        
    except CustomUser.DoesNotExist:
        logger.error(f"User {user_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error sending password reset email: {str(e)}")
        raise


@shared_task
def send_welcome_email(user_id):
    """Send welcome email to new user"""
    try:
        user = CustomUser.objects.get(id=user_id)
        
        subject = "Welcome to Nexus Messaging Platform"
        message = f"""
        Hello {user.first_name or user.email},
        
        Welcome to Nexus! Your account has been successfully created.
        
        You can now start connecting your messaging platforms and managing customer conversations with AI assistance.
        
        Get started by:
        1. Setting up your first bridge connection
        2. Configuring your AI assistant
        3. Inviting team members
        
        Visit your dashboard: {settings.FRONTEND_URL}/dashboard
        
        Best regards,
        The Nexus Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        return f"Welcome email sent to {user.email}"
        
    except CustomUser.DoesNotExist:
        logger.error(f"User {user_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error sending welcome email: {str(e)}")
        raise


@shared_task
def update_user_activity(user_id):
    """Update user last activity"""
    try:
        user = CustomUser.objects.get(id=user_id)
        user.last_activity = timezone.now()
        user.save(update_fields=['last_activity'])
        
        return f"Updated activity for {user.email}"
        
    except CustomUser.DoesNotExist:
        logger.error(f"User {user_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error updating user activity: {str(e)}")
        raise
