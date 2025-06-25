from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from companies.models import Company, CompanySettings
import uuid

User = get_user_model()


class Command(BaseCommand):
    help = 'Create a demo company with sample data for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-name',
            type=str,
            default='Demo Company',
            help='Name of the demo company',
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            default='admin@democompany.com',
            help='Email for the admin user',
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            default='demo123456',
            help='Password for the admin user',
        )

    def handle(self, *args, **options):
        company_name = options['company_name']
        admin_email = options['admin_email']
        admin_password = options['admin_password']

        self.stdout.write(f'Creating demo company: {company_name}')

        # Create company
        company, created = Company.objects.get_or_create(
            slug='demo-company',
            defaults={
                'name': company_name,
                'email': admin_email,
                'domain': 'democompany.com',
                'size': 'small',
                'industry': 'Technology',
                'description': 'Demo company for testing Nexus platform',
                'plan': 'professional',
                'status': 'active',
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created company: {company.name}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Company already exists: {company.name}')
            )

        # Create company settings
        settings_obj, settings_created = CompanySettings.objects.get_or_create(
            company=company,
            defaults={
                'ai_enabled': True,
                'ai_provider': 'google',
                'ai_model': 'gemini-pro',
                'message_retention_days': 90,
                'auto_create_rooms': True,
                'bridge_auto_reconnect': True,
            }
        )

        if settings_created:
            self.stdout.write(
                self.style.SUCCESS('Created company settings')
            )

        # Create admin user
        admin_user, user_created = User.objects.get_or_create(
            email=admin_email,
            defaults={
                'first_name': 'Demo',
                'last_name': 'Admin',
                'company': company,
                'role': 'owner',
                'is_staff': True,
            }
        )

        if user_created:
            admin_user.set_password(admin_password)
            admin_user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Created admin user: {admin_email}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Admin user already exists: {admin_email}')
            )

        # Create some sample users
        sample_users = [
            {
                'email': 'manager@democompany.com',
                'first_name': 'Demo',
                'last_name': 'Manager',
                'role': 'manager',
            },
            {
                'email': 'agent1@democompany.com',
                'first_name': 'Agent',
                'last_name': 'One',
                'role': 'agent',
            },
            {
                'email': 'agent2@democompany.com',
                'first_name': 'Agent',
                'last_name': 'Two',
                'role': 'agent',
            },
        ]

        for user_data in sample_users:
            user, created = User.objects.get_or_create(
                email=user_data['email'],
                defaults={
                    **user_data,
                    'company': company,
                }
            )
            
            if created:
                user.set_password('demo123456')
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Created user: {user.email}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDemo company setup complete!\n'
                f'Company: {company.name}\n'
                f'Admin: {admin_email} / {admin_password}\n'
                f'Additional users created with password: demo123456\n'
            )
        )
