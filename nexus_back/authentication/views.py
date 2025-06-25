from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
import secrets
import pyotp
import qrcode
import io
import base64

from .models import CustomUser, UserRole, MFADevice, UserSession
from .serializers import (
    UserSerializer, 
    UserRegistrationSerializer, 
    UserLoginSerializer,
    UserProfileSerializer,
    MFADeviceSerializer,
    ChangePasswordSerializer
)
from .permissions import IsSameUserOrAdmin
from companies.models import Company, CompanyInvitation


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsSameUserOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return CustomUser.objects.all()
        elif user.role in ['owner', 'admin']:
            return CustomUser.objects.filter(company=user.company)
        else:
            return CustomUser.objects.filter(id=user.id)

    def get_serializer_class(self):
        if self.action == 'register':
            return UserRegistrationSerializer
        elif self.action == 'profile':
            return UserProfileSerializer
        elif self.action == 'change_password':
            return ChangePasswordSerializer
        return UserSerializer

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def register(self, request):
        """Register a new user"""
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
        """User login"""
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            mfa_code = serializer.validated_data.get('mfa_code')
            
            user = authenticate(email=email, password=password)
            if not user:
                return Response(
                    {'error': 'Invalid credentials'}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            if not user.is_active:
                return Response(
                    {'error': 'Account is deactivated'}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Check MFA if enabled
            if user.mfa_enabled:
                if not mfa_code:
                    return Response(
                        {'error': 'MFA code required', 'mfa_required': True}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if not self._verify_mfa_code(user, mfa_code):
                    return Response(
                        {'error': 'Invalid MFA code'}, 
                        status=status.HTTP_401_UNAUTHORIZED
                    )
            
            # Update last login
            user.last_login = timezone.now()
            user.save()
            
            # Create session
            UserSession.objects.create(
                user=user,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def logout(self, request):
        """User logout"""
        try:
            # Invalidate the refresh token
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            # End user session
            ip_address = self._get_client_ip(request)
            UserSession.objects.filter(
                user=request.user,
                ip_address=ip_address,
                ended_at__isnull=True
            ).update(ended_at=timezone.now())
            
            return Response({'message': 'Logout successful'})
        except Exception as e:
            return Response(
                {'error': 'Logout failed'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get', 'patch'])
    def profile(self, request):
        """Get or update user profile"""
        if request.method == 'GET':
            serializer = UserProfileSerializer(request.user)
            return Response(serializer.data)
        
        elif request.method == 'PATCH':
            serializer = UserProfileSerializer(
                request.user, 
                data=request.data, 
                partial=True
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change user password"""
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            
            # Check old password
            if not user.check_password(serializer.validated_data['old_password']):
                return Response(
                    {'error': 'Invalid old password'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Set new password
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            
            return Response({'message': 'Password changed successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def setup_mfa(self, request):
        """Setup MFA for user"""
        user = request.user
        
        # Generate secret
        secret = pyotp.random_base32()
        
        # Create TOTP
        totp = pyotp.TOTP(secret)
        
        # Generate QR code
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name="Nexus Messaging Platform"
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_code_data = base64.b64encode(buffer.getvalue()).decode()
        
        # Store secret temporarily (user needs to verify)
        MFADevice.objects.update_or_create(
            user=user,
            defaults={
                'secret': secret,
                'is_active': False
            }
        )
        
        return Response({
            'secret': secret,
            'qr_code': f"data:image/png;base64,{qr_code_data}",
            'provisioning_uri': provisioning_uri
        })

    @action(detail=False, methods=['post'])
    def verify_mfa_setup(self, request):
        """Verify MFA setup with code"""
        user = request.user
        code = request.data.get('code')
        
        if not code:
            return Response(
                {'error': 'MFA code is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            mfa_device = MFADevice.objects.get(user=user)
            totp = pyotp.TOTP(mfa_device.secret)
            
            if totp.verify(code):
                mfa_device.is_active = True
                mfa_device.save()
                
                user.mfa_enabled = True
                user.save()
                
                return Response({'message': 'MFA setup completed successfully'})
            else:
                return Response(
                    {'error': 'Invalid MFA code'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except MFADevice.DoesNotExist:
            return Response(
                {'error': 'MFA setup not initiated'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def disable_mfa(self, request):
        """Disable MFA for user"""
        user = request.user
        password = request.data.get('password')
        
        if not password:
            return Response(
                {'error': 'Password is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not user.check_password(password):
            return Response(
                {'error': 'Invalid password'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.mfa_enabled = False
        user.save()
        
        MFADevice.objects.filter(user=user).delete()
        
        return Response({'message': 'MFA disabled successfully'})

    @action(detail=False, methods=['get'])
    def sessions(self, request):
        """Get user sessions"""
        sessions = UserSession.objects.filter(user=request.user).order_by('-created_at')
        
        sessions_data = []
        for session in sessions:
            sessions_data.append({
                'id': session.id,
                'ip_address': session.ip_address,
                'user_agent': session.user_agent,
                'created_at': session.created_at,
                'last_activity': session.last_activity,
                'ended_at': session.ended_at,
                'is_current': session.ip_address == self._get_client_ip(request)
            })
        
        return Response(sessions_data)

    @action(detail=False, methods=['post'])
    def end_session(self, request):
        """End a specific session"""
        session_id = request.data.get('session_id')
        
        if not session_id:
            return Response(
                {'error': 'session_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            session = UserSession.objects.get(
                id=session_id, 
                user=request.user,
                ended_at__isnull=True
            )
            session.ended_at = timezone.now()
            session.save()
            
            return Response({'message': 'Session ended successfully'})
        except UserSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    def _verify_mfa_code(self, user, code):
        """Verify MFA code for user"""
        try:
            mfa_device = MFADevice.objects.get(user=user, is_active=True)
            totp = pyotp.TOTP(mfa_device.secret)
            return totp.verify(code)
        except MFADevice.DoesNotExist:
            return False

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def accept_invitation(request, token):
    """Accept company invitation using token"""
    try:
        invitation = CompanyInvitation.objects.get(token=token, status='pending')
        
        if invitation.is_expired:
            invitation.status = 'expired'
            invitation.save()
            return Response(
                {'error': 'Invitation has expired'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user exists
        try:
            user = CustomUser.objects.get(email=invitation.email)
        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'Please register first with the invited email'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Accept invitation
        user.company = invitation.company
        user.role = invitation.role
        user.save()
        
        invitation.status = 'accepted'
        invitation.invited_user = user
        invitation.accepted_at = timezone.now()
        invitation.save()
        
        return Response({
            'message': 'Invitation accepted successfully',
            'company': invitation.company.name
        })
        
    except CompanyInvitation.DoesNotExist:
        return Response(
            {'error': 'Invalid invitation token'}, 
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def invitation_details(request, token):
    """Get invitation details"""
    try:
        invitation = CompanyInvitation.objects.get(token=token, status='pending')
        
        if invitation.is_expired:
            return Response(
                {'error': 'Invitation has expired'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'company_name': invitation.company.name,
            'role': invitation.role,
            'invited_by': f"{invitation.invited_by.first_name} {invitation.invited_by.last_name}".strip() or invitation.invited_by.email,
            'expires_at': invitation.expires_at
        })
        
    except CompanyInvitation.DoesNotExist:
        return Response(
            {'error': 'Invalid invitation token'}, 
            status=status.HTTP_404_NOT_FOUND
        )
