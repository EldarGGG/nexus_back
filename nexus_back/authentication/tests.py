from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch, MagicMock
import uuid

from .models import CustomUser, UserRole, MFADevice, UserSession, EmailVerificationToken
from companies.models import Company, CompanySettings

User = get_user_model()


class CustomUserModelTest(TestCase):
    """Test CustomUser model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            slug="test-company",
            industry="technology",
            size="small"
        )

    def test_create_user(self):
        """Test creating a regular user"""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            company=self.company
        )
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("testpass123"))
        self.assertEqual(user.company, self.company)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        """Test creating a superuser"""
        user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass123"
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_user_str_representation(self):
        """Test user string representation"""
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            company=self.company
        )
        self.assertEqual(str(user), "testuser")


class UserRoleModelTest(TestCase):
    """Test UserRole model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            slug="test-company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            company=self.company
        )

    def test_create_user_role(self):
        """Test creating a user role"""
        role = UserRole.objects.create(
            user=self.user,
            role="admin",
            permissions={"can_manage_users": True}
        )
        self.assertEqual(role.user, self.user)
        self.assertEqual(role.role, "admin")
        self.assertTrue(role.permissions["can_manage_users"])

    def test_role_choices_validation(self):
        """Test that only valid role choices are accepted"""
        valid_roles = ['owner', 'admin', 'manager', 'agent', 'viewer']
        for role in valid_roles:
            user_role = UserRole(user=self.user, role=role)
            user_role.full_clean()  # Should not raise ValidationError


class MFADeviceModelTest(TestCase):
    """Test MFADevice model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            slug="test-company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            company=self.company
        )

    def test_create_mfa_device(self):
        """Test creating an MFA device"""
        device = MFADevice.objects.create(
            user=self.user,
            device_name="Test Device",
            secret_key="test_secret_key",
            backup_codes=["123456", "789012"]
        )
        self.assertEqual(device.user, self.user)
        self.assertEqual(device.device_name, "Test Device")
        self.assertTrue(device.is_active)
        self.assertEqual(len(device.backup_codes), 2)


class AuthenticationAPITest(APITestCase):
    """Test authentication API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Test Company",
            slug="test-company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            company=self.company
        )

    def test_jwt_token_obtain(self):
        """Test JWT token obtain endpoint"""
        url = reverse('authentication:token_obtain_pair')
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_jwt_token_refresh(self):
        """Test JWT token refresh endpoint"""
        refresh = RefreshToken.for_user(self.user)
        url = reverse('authentication:token_refresh')
        data = {'refresh': str(refresh)}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)


class UserSessionTest(TestCase):
    """Test user session tracking"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            slug="test-company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            company=self.company
        )

    def test_create_user_session(self):
        """Test creating a user session"""
        session = UserSession.objects.create(
            user=self.user,
            ip_address="192.168.1.1",
            user_agent="Test Browser"
        )
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.ip_address, "192.168.1.1")
        self.assertTrue(session.is_active)
