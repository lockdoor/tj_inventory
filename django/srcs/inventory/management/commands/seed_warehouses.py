"""
Management command: seed_warehouses

Seeds the database with mockup warehouses for testing and demonstration.
Usage:
    python manage.py seed_warehouses
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from inventory.services.warehouse_service import WarehouseService
from inventory.models import Warehouse

MOCK_WAREHOUSES = [
    {
        'name': 'Central Distribution Hub',
        'code': 'WH-CN',
        'note': 'Main logistics center for all regional operations.',
        'status': 'active'
    },
    {
        'name': 'North East Port Terminal',
        'code': 'WH-NE',
        'note': 'Secondary facility for maritime inbound shipments.',
        'status': 'active'
    },
    {
        'name': 'South West Strategic Hub',
        'code': 'WH-SW',
        'note': 'Last-mile delivery center for southern territories.',
        'status': 'active'
    },
    {
        'name': 'Old Storage Unit (Deactivated)',
        'code': 'WH-OLD',
        'note': 'Legacy facility currently being decommissioned.',
        'status': 'inactive'
    },
    {
        'name': 'Accidental Record',
        'code': 'WH-TRASH',
        'note': 'Item destined for the trash ledger.',
        'status': 'inactive',
        'is_deleted': True
    },
]

class Command(BaseCommand):
    help = 'Seed the inventory app with mockup warehouse data.'

    def handle(self, *args, **options):
        # 1. Get a user
        user = User.objects.filter(groups__name='executive').first() or User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR('  No users found. Run seed_groups or create a user first.'))
            return

        self.stdout.write(self.style.NOTICE(f'\nSeeding Warehouses as user: {user.username}...'))

        # 2. Process mock data
        created_count = 0
        for data in MOCK_WAREHOUSES:
            # Check if it already exists
            if Warehouse.objects.filter(code=data['code']).exists():
                self.stdout.write(self.style.WARNING(f'  ⚠ Skipping {data["name"]} ({data["code"]}) - already exists.'))
                continue

            try:
                # Use service for creation
                warehouse = WarehouseService.create(
                    name=data['name'],
                    code=data['code'],
                    user=user,
                    note=data.get('note', ''),
                    status=data.get('status', 'active')
                )
                
                # Handle soft-delete if specified in seed
                if data.get('is_deleted'):
                    WarehouseService.soft_delete(warehouse, user=user)
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created & Trashed {data["name"]} ({data["code"]})'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created {data["name"]} ({data["code"]})'))
                
                created_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✘ Error creating {data["name"]}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'\nDone. Created {created_count} warehouses.'))
