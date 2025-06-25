from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q
from django.core.mail import send_mail
from django.conf import settings
import secrets
import hashlib

from .models import Company, CompanySettings, CompanyInvitation
from .serializers import (
    CompanySerializer, 
    CompanyDetailSerializer, 
    CompanySettingsSerializer,
    CompanyInvitationSerializer,
    CompanyOnboardingSerializer
)
from authentication.models import CustomUser
from authentication.permissions import IsCompanyAdminOrReadOnly, IsCompanyMember


class CompanyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing companies
    """
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyMember]
    lookup_field = 'slug'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Company.objects.all()
        return Company.objects.filter(users=user)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CompanyDetailSerializer
        elif self.action == 'onboard':
            return CompanyOnboardingSerializer
        return CompanySerializer

    def perform_create(self, serializer):
        """Create a new company and set the current user as owner"""
        company = serializer.save()
        
        # Create default settings
        CompanySettings.objects.create(company=company)
        
        # Add current user as company owner
        self.request.user.company = company
        self.request.user.role = 'owner'
        self.request.user.save()

    @action(detail=True, methods=['get', 'patch'])
    def settings(self, request, slug=None):
        """Get or update company settings"""
        company = self.get_object()
        settings_obj, created = CompanySettings.objects.get_or_create(company=company)
        
        if request.method == 'GET':
            serializer = CompanySettingsSerializer(settings_obj)
            return Response(serializer.data)
        
        elif request.method == 'PATCH':
            serializer = CompanySettingsSerializer(settings_obj, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def invite_user(self, request, slug=None):
        """Invite a user to join the company"""
        company = self.get_object()
        
        # Check permission
        if not request.user.role in ['owner', 'admin']:
            return Response(
                {'error': 'Only owners and admins can invite users'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        email = request.data.get('email')
        role = request.data.get('role', 'agent')
        
        if not email:
            return Response(
                {'error': 'Email is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user is already a member
        if CustomUser.objects.filter(email=email, company=company).exists():
            return Response(
                {'error': 'User is already a member of this company'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if invitation already exists
        existing_invitation = CompanyInvitation.objects.filter(
            company=company, 
            email=email, 
            status='pending'
        ).first()
        
        if existing_invitation:
            return Response(
                {'error': 'Invitation already sent to this email'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create invitation
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timezone.timedelta(days=7)
        
        invitation = CompanyInvitation.objects.create(
            company=company,
            email=email,
            role=role,
            invited_by=request.user,
            token=token,
            expires_at=expires_at
        )
        
        # Send invitation email
        self._send_invitation_email(invitation)
        
        serializer = CompanyInvitationSerializer(invitation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def invitations(self, request, slug=None):
        """List company invitations"""
        company = self.get_object()
        invitations = company.invitations.all().order_by('-created_at')
        serializer = CompanyInvitationSerializer(invitations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def members(self, request, slug=None):
        """List company members"""
        company = self.get_object()
        members = company.users.all().order_by('role', 'first_name', 'last_name')
        
        members_data = []
        for member in members:
            members_data.append({
                'id': member.id,
                'email': member.email,
                'first_name': member.first_name,
                'last_name': member.last_name,
                'role': member.role,
                'is_active': member.is_active,
                'last_login': member.last_login,
                'date_joined': member.date_joined,
            })
        
        return Response(members_data)

    @action(detail=True, methods=['post'])
    def remove_member(self, request, slug=None):
        """Remove a member from the company"""
        company = self.get_object()
        
        if not request.user.role in ['owner', 'admin']:
            return Response(
                {'error': 'Only owners and admins can remove members'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        member = get_object_or_404(CustomUser, id=user_id, company=company)
        
        # Cannot remove owner
        if member.role == 'owner':
            return Response(
                {'error': 'Cannot remove company owner'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Remove member
        member.company = None
        member.role = None
        member.save()
        
        return Response({'message': 'Member removed successfully'})

    @action(detail=True, methods=['get'])
    def stats(self, request, slug=None):
        """Get company statistics"""
        company = self.get_object()
        
        stats = {
            'total_users': company.users.count(),
            'active_users': company.users.filter(is_active=True).count(),
            'total_bridges': company.bridges.count(),
            'active_bridges': company.bridges.filter(status='connected').count(),
            'total_rooms': company.matrix_rooms.count(),
            'messages_this_month': company.messages.filter(
                created_at__gte=timezone.now().replace(day=1)
            ).count(),
            'ai_requests_this_month': company.ai_requests.filter(
                created_at__gte=timezone.now().replace(day=1)
            ).count(),
        }
        
        return Response(stats)

    def _send_invitation_email(self, invitation):
        """Send invitation email to user"""
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
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [invitation.email],
                fail_silently=False,
            )
        except Exception as e:
            # Log the error but don't fail the invitation creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send invitation email to {invitation.email}: {str(e)}")


class CompanyInvitationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing company invitations
    """
    serializer_class = CompanyInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'token'

    def get_queryset(self):
        if self.request.user.is_superuser:
            return CompanyInvitation.objects.all()
        return CompanyInvitation.objects.filter(
            Q(invited_by=self.request.user) | Q(email=self.request.user.email)
        )

    @action(detail=True, methods=['post'])
    def accept(self, request, token=None):
        """Accept a company invitation"""
        invitation = self.get_object()
        
        # Check if invitation is valid
        if invitation.status != 'pending':
            return Response(
                {'error': 'Invitation is no longer valid'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if invitation.is_expired:
            invitation.status = 'expired'
            invitation.save()
            return Response(
                {'error': 'Invitation has expired'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user email matches invitation
        if request.user.email != invitation.email:
            return Response(
                {'error': 'Email mismatch'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Accept invitation
        request.user.company = invitation.company
        request.user.role = invitation.role
        request.user.save()
        
        invitation.status = 'accepted'
        invitation.invited_user = request.user
        invitation.accepted_at = timezone.now()
        invitation.save()
        
        return Response({'message': 'Invitation accepted successfully'})

    @action(detail=True, methods=['post'])
    def reject(self, request, token=None):
        """Reject a company invitation"""
        invitation = self.get_object()
        
        if invitation.status != 'pending':
            return Response(
                {'error': 'Invitation is no longer valid'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        invitation.status = 'rejected'
        invitation.save()
        
        return Response({'message': 'Invitation rejected'})
