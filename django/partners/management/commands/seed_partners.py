"""
Management command: seed_partners

Seeds the database with mockup partners for testing and demonstration.
Usage:
    python manage.py seed_partners
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from partners.services.partner_service import PartnerService
from partners.models import Partner

MOCK_PARTNERS = [
    # Suppliers
    {
        'name': 'TechLogistics Corp', 
        'code': 'SUP-TECH', 
        'is_supplier': True, 
        'is_customer': False,
        'contact_name': 'John Tech',
        'email': 'supply@techlogistics.com',
        'note': 'Main electronics supplier.'
    },
    {
        'name': 'Global Freight Solutions', 
        'code': 'SUP-GFS', 
        'is_supplier': True, 
        'is_customer': False,
        'contact_name': 'Sarah Freight',
        'phone': '+1-555-0199',
        'note': 'International shipping partner.'
    },
    {
        'name': 'Pioneer Parts Ltd', 
        'code': 'SUP-PION', 
        'is_supplier': True, 
        'is_customer': False,
        'contact_name': 'Mike Parts',
        'email': 'orders@pioneer.com'
    },
    
    # Customers
    {
        'name': 'Retail Giant Inc', 
        'code': 'CUST-RG', 
        'is_supplier': False, 
        'is_customer': True,
        'contact_name': 'Robert Retail',
        'email': 'procurement@retailgiant.com',
        'note': 'Key account manager: Jane Doe.'
    },
    {
        'name': 'City Electronics Store', 
        'code': 'CUST-CES', 
        'is_supplier': False, 
        'is_customer': True,
        'contact_name': 'Charlie City',
        'phone': '02-123-4567'
    },
    {
        'name': 'Online Market Hub', 
        'code': 'CUST-OMH', 
        'is_supplier': False, 
        'is_customer': True,
        'email': 'sales@onlinemarket.com'
    },
    
    # Both Roles
    {
        'name': 'Elite Distrib Agency', 
        'code': 'PART-ELITE', 
        'is_supplier': True, 
        'is_customer': True,
        'contact_name': 'Elena Elite',
        'note': 'Acts as both distributor and major purchaser.'
    },
]

class Command(BaseCommand):
    help = 'Seed the partners app with mockup data.'

    def handle(self, *args, **options):
        # 1. Get a user
        user = User.objects.filter(is_staff=True).first() or User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR('  No staff users found. Please create a superuser first.'))
            return

        self.stdout.write(self.style.NOTICE(f'\nSeeding Partners as user: {user.username}...'))

        # 2. Process mock data
        created_count = 0
        for data in MOCK_PARTNERS:
            if Partner.objects.filter(code=data['code']).exists():
                self.stdout.write(self.style.WARNING(f'  ⚠ Skipping {data["name"]} ({data["code"]}) - already exists.'))
                continue

            try:
                PartnerService.create(
                    name=data['name'],
                    code=data['code'],
                    user=user,
                    is_supplier=data['is_supplier'],
                    is_customer=data['is_customer'],
                    contact_name=data.get('contact_name', ''),
                    email=data.get('email', ''),
                    phone=data.get('phone', ''),
                    note=data.get('note', '')
                )
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created {data["name"]} ({data["code"]})'))
                created_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✘ Error creating {data["name"]}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'\nDone. Created {created_count} partners.'))
