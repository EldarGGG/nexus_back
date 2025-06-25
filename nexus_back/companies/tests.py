from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from unittest.mock import patch, MagicMock
from decimal import Decimal

from .models import Company, CompanySettings, CompanyInvitation
from authentication.models import UserRole

User = get_user_model()


class CompanyModelTest(TestCase):
    """Test Company model functionality"""

    def test_create_company(self):
        """Test creating a company"""
        company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small",
            website="https://example.com"
        )
        self.assertEqual(company.name, "Test Company")
        self.assertEqual(company.slug, "test-company")
        self.assertTrue(company.is_active)
        self.assertEqual(company.plan, "trial")

    def test_company_slug_generation(self):
        """Test automatic slug generation"""
        company = Company.objects.create(
            name="My Amazing Company Ltd!",
            industry="technology",
            size="small"
        )
        self.assertEqual(company.slug, "my-amazing-company-ltd")

    def test_company_str_representation(self):
        """Test company string representation"""
        company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.assertEqual(str(company), "Test Company")

    def test_trial_expiration_default(self):
        """Test trial expiration is set by default"""
        company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.assertIsNotNone(company.trial_expires_at)

    def test_unique_slug_constraint(self):
        """Test that company slugs are unique"""
        Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        
        # Second company with same name should get different slug
        company2 = Company.objects.create(
            name="Test Company",
            industry="technology",
            company_size="50-100"
        )
        self.assertNotEqual(company2.slug, "test-company")


class CompanySettingsModelTest(TestCase):
    """Test CompanySettings model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )

    def test_create_company_settings(self):
        """Test creating company settings"""
        settings = CompanySettings.objects.create(
            company=self.company,
            business_hours={"monday": {"start": "09:00", "end": "17:00"}},
            ai_enabled=True,
            auto_response_enabled=True
        )
        self.assertEqual(settings.company, self.company)
        self.assertTrue(settings.ai_enabled)
        self.assertTrue(settings.auto_response_enabled)

    def test_default_settings_values(self):
        """Test default settings values"""
        settings = CompanySettings.objects.create(company=self.company)
        self.assertIsInstance(settings.business_hours, dict)
        self.assertIsInstance(settings.webhook_settings, dict)
        self.assertIsInstance(settings.notification_settings, dict)


class CompanyInvitationModelTest(TestCase):
    """Test CompanyInvitation model functionality"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.inviter = User.objects.create_user(
            username="inviter",
            email="inviter@example.com",
            company=self.company
        )

    def test_create_company_invitation(self):
        """Test creating a company invitation"""
        invitation = CompanyInvitation.objects.create(
            company=self.company,
            email="newuser@example.com",
            invited_by=self.inviter,
            role="agent"
        )
        self.assertEqual(invitation.company, self.company)
        self.assertEqual(invitation.email, "newuser@example.com")
        self.assertEqual(invitation.status, "pending")
        self.assertIsNotNone(invitation.token)

    def test_invitation_expiration(self):
        """Test invitation expiration"""
        invitation = CompanyInvitation.objects.create(
            company=self.company,
            email="newuser@example.com",
            invited_by=self.inviter,
            role="agent"
        )
        self.assertIsNotNone(invitation.expires_at)

    def test_invitation_str_representation(self):
        """Test invitation string representation"""
        invitation = CompanyInvitation.objects.create(
            company=self.company,
            email="newuser@example.com",
            invited_by=self.inviter,
            role="agent"
        )
        expected = f"{self.company.name} - newuser@example.com"
        self.assertEqual(str(invitation), expected)


class CompanyAPITest(APITestCase):
    """Test Company API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            company=self.company
        )
        UserRole.objects.create(
            user=self.user,
            role="owner",
            permissions={"can_manage_settings": True}
        )
        
        # Authenticate user
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_get_company_list(self):
        """Test getting company list"""
        url = reverse('companies:company-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], "Test Company")

    def test_get_company_detail(self):
        """Test getting company detail"""
        url = reverse('companies:company-detail', kwargs={'slug': self.company.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], "Test Company")

    def test_update_company(self):
        """Test updating company"""
        url = reverse('companies:company-detail', kwargs={'slug': self.company.slug})
        data = {
            'name': 'Updated Company Name',
            'website': 'https://updated.com'
        }
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, 'Updated Company Name')

    def test_company_multi_tenant_isolation(self):
        """Test that users can only see their own company"""
        # Create another company and user
        other_company = Company.objects.create(
            name="Other Company",
            industry="finance",
            company_size="100-500"
        )
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            company=other_company
        )
        
        # Try to access other company
        url = reverse('companies:company-detail', kwargs={'slug': other_company.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_company_settings_endpoint(self):
        """Test company settings endpoint"""
        CompanySettings.objects.create(
            company=self.company,
            ai_enabled=True
        )
        
        url = reverse('companies:company-settings', kwargs={'slug': self.company.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['ai_enabled'])


class CompanyOnboardingTest(TestCase):
    """Test company onboarding process"""

    @patch('companies.tasks.send_welcome_email.delay')
    def test_company_onboarding_flow(self, mock_send_email):
        """Test complete company onboarding flow"""
        from companies.serializers import CompanyOnboardingSerializer
        
        data = {
            'company_name': 'New Startup',
            'industry': 'technology',
            'company_size': '1-10',
            'website': 'https://newstartup.com',
            'admin_first_name': 'John',
            'admin_last_name': 'Doe',
            'admin_email': 'john@newstartup.com',
            'admin_phone': '+1234567890'
        }
        
        serializer = CompanyOnboardingSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # This would typically be called in a view
        # result = serializer.save()
        # mock_send_email.assert_called_once()


class CompanyInvitationAPITest(APITestCase):
    """Test Company Invitation API"""

    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            company=self.company
        )
        UserRole.objects.create(
            user=self.user,
            role="admin",
            permissions={"can_manage_users": True}
        )
        
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    @patch('companies.tasks.send_invitation_email.delay')
    def test_send_invitation(self, mock_send_email):
        """Test sending user invitation"""
        url = reverse('companies:company-invite-user', kwargs={'slug': self.company.slug})
        data = {
            'email': 'newuser@example.com',
            'role': 'agent'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check invitation was created
        invitation = CompanyInvitation.objects.get(email='newuser@example.com')
        self.assertEqual(invitation.company, self.company)
        self.assertEqual(invitation.role, 'agent')
        
        # Check email task was called
        mock_send_email.assert_called_once()

    def test_accept_invitation(self):
        """Test accepting an invitation"""
        invitation = CompanyInvitation.objects.create(
            company=self.company,
            email="invited@example.com",
            invited_by=self.user,
            role="agent"
        )
        
        # Remove authentication for this test
        self.client.credentials()
        
        url = reverse('accept_invitation', kwargs={'token': invitation.token})
        data = {
            'password': 'newpassword123',
            'first_name': 'Invited',
            'last_name': 'User'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check user was created
        new_user = User.objects.get(email='invited@example.com')
        self.assertEqual(new_user.company, self.company)
        
        # Check invitation was marked as accepted
        invitation.refresh_from_db()
        self.assertTrue(invitation.is_accepted)


class CompanyMetricsTest(TestCase):
    """Test company metrics and analytics"""

    def setUp(self):
        self.company = Company.objects.create(
            name="Test Company",
            industry="technology",
            size="small"
        )

    def test_user_count_metric(self):
        """Test counting company users"""
        # Create users
        User.objects.create_user(
            username="user1",
            email="user1@example.com",
            company=self.company
        )
        User.objects.create_user(
            username="user2",
            email="user2@example.com",
            company=self.company
        )
        
        user_count = self.company.users.count()
        self.assertEqual(user_count, 2)

    def test_company_activity_tracking(self):
        """Test tracking company activity"""
        # This would test activity tracking functionality
        # Implementation depends on your activity tracking system
        pass
