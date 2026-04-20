"""
Management command: seed_catalog

Seeds the database with mockup categories for testing and demonstration.
Usage:
    python manage.py seed_catalog
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from catalog.services import CategoryService
from catalog.models import Category

MOCK_CATEGORIES = [
    # Top-level categories
    {'name': 'Electronics', 'code': 'ELEC', 'parent': None, 'note': 'All electronic devices and accessories.'},
    {'name': 'Furniture', 'code': 'FURN', 'parent': None, 'note': 'Office and warehouse furniture.'},
    {'name': 'Office Supplies', 'code': 'OFFICE', 'parent': None, 'note': 'General office stationery.'},
    
    # Sub-categories for Electronics
    {'name': 'Laptops', 'code': 'LAP', 'parent_code': 'ELEC', 'note': 'Business and personal laptops.'},
    {'name': 'Monitors', 'code': 'MON', 'parent_code': 'ELEC', 'note': 'High-resolution displays.'},
    {'name': 'Printers', 'code': 'PRIN', 'parent_code': 'ELEC', 'note': 'Laser and inkjet printers.'},
    
    # Sub-categories for Furniture
    {'name': 'Tables', 'code': 'TAB', 'parent_code': 'FURN', 'note': 'Workstations and meeting tables.'},
    {'name': 'Chairs', 'code': 'CHA', 'parent_code': 'FURN', 'note': 'Ergonomic office chairs.'},
]

class Command(BaseCommand):
    help = 'Seed the catalog app with mockup data.'

    def handle(self, *args, **options):
        # 1. Get a user to assign as the creator
        user = User.objects.filter(groups__name='executive').first() or User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR('  No users found in database. Please create a user or run seed_groups first.'))
            return

        self.stdout.write(self.style.NOTICE(f'\nSeeding Catalog as user: {user.username}...'))

        # 2. Process mock data
        created_count = 0
        for data in MOCK_CATEGORIES:
            # Check if it already exists
            if Category.objects.filter(code=data['code']).exists():
                self.stdout.write(self.style.WARNING(f'  ⚠ Skipping {data["name"]} ({data["code"]}) - already exists.'))
                continue

            # Resolve parent if parent_code was provided
            parent = None
            if 'parent_code' in data:
                parent = Category.objects.filter(code=data['parent_code']).first()

            try:
                # Use CategoryService for consistent creation logic
                CategoryService.create(
                    name=data['name'],
                    code=data['code'],
                    user=user,
                    parent=parent,
                    note=data.get('note', '')
                )
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created {data["name"]} ({data["code"]})'))
                created_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✘ Error creating {data["name"]}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'\nDone. Created {created_count} categories.'))
