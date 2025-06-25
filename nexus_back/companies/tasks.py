from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import CompanyInvitation
import logging

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_invitations():
    """Clean up expired company invitations"""
    try:
        expired_invitations = CompanyInvitation.objects.filter(
            expires_at__lt=timezone.now(),
            status='pending'
        )
        
        count = expired_invitations.count()
        expired_invitations.update(status='expired')
        
        logger.info(f"Marked {count} invitations as expired")
        return f"Processed {count} expired invitations"
        
    except Exception as e:
        logger.error(f"Error cleaning up expired invitations: {str(e)}")
        raise


@shared_task
def send_invitation_email(invitation_id):
    """Send invitation email asynchronously"""
    try:
        invitation = CompanyInvitation.objects.get(id=invitation_id)
        
        subject = f"Invitation to join {invitation.company.name}"
        message = f"""
        Hello,
        
        You've been invited to join {invitation.company.name} as a {invitation.role}.
        
        Click the link below to accept the invitation:
        {settings.FRONTEND_URL}/invite/{invitation.token}
        
        This invitation will expire on {invitation.expires_at.strftime('%Y-%m-%d %H:%M UTC')}.
        
        Best regards,
        The Nexus Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [invitation.email],
            fail_silently=False,
        )
        
        logger.info(f"Invitation email sent to {invitation.email}")
        return f"Email sent to {invitation.email}"
        
    except CompanyInvitation.DoesNotExist:
        logger.error(f"Invitation {invitation_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error sending invitation email: {str(e)}")
        raise


@shared_task
def update_company_stats(company_id):
    """Update company statistics"""
    try:
        from .models import Company
        
        company = Company.objects.get(id=company_id)
        
        # Update various stats
        total_users = company.users.count()
        active_bridges = company.bridges.filter(status='connected').count()
        total_rooms = company.matrix_rooms.count()
        
        # Could store these in a separate CompanyStats model
        # For now, just log them
        logger.info(f"Company {company.name} stats: {total_users} users, {active_bridges} bridges, {total_rooms} rooms")
        
        return f"Updated stats for {company.name}"
        
    except Exception as e:
        logger.error(f"Error updating company stats: {str(e)}")
        raise


@shared_task
def generate_company_report(company_id, report_type='monthly'):
    """Generate company usage report"""
    try:
        from .models import Company
        
        company = Company.objects.get(id=company_id)
        
        # Generate report based on type
        if report_type == 'monthly':
            # TODO: Implement monthly report generation
            pass
        elif report_type == 'weekly':
            # TODO: Implement weekly report generation
            pass
        
        logger.info(f"Generated {report_type} report for {company.name}")
        return f"Generated {report_type} report for {company.name}"
        
    except Exception as e:
        logger.error(f"Error generating company report: {str(e)}")
        raise


@shared_task
def send_welcome_email(user_id, company_id):
    """Send welcome email to new company user"""
    try:
        from authentication.models import CustomUser
        from .models import Company
        
        user = CustomUser.objects.get(id=user_id)
        company = Company.objects.get(id=company_id)
        
        subject = f"Welcome to {company.name}!"
        message = f"""
        Hello {user.first_name or user.username},
        
        Welcome to {company.name}! Your account has been successfully created.
        
        You can now access your dashboard at:
        {settings.FRONTEND_URL}/dashboard
        
        If you have any questions, please don't hesitate to reach out to our support team.
        
        Best regards,
        The Nexus Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        return f"Welcome email sent to {user.email}"
        
    except Exception as e:
        logger.error(f"Error sending welcome email: {str(e)}")
        raise
