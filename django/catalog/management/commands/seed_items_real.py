import os
import json
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from django.conf import settings
from catalog.models import Category, Item
from catalog.services.item_service import ItemService

class Command(BaseCommand):
    help = 'Seed real items from private/data/tj_items.json'

    def handle(self, *args, **options):
        # Path to the data file
        data_path = os.path.join(settings.BASE_DIR, '..', 'private', 'data', 'tj_items.json')
        
        if not os.path.exists(data_path):
            raise CommandError(
                f'Real item data not found at: {data_path}\n'
                'Please export your business data to this path before seeding.'
            )

        self.stdout.write(self.style.NOTICE(f'Reading data from {data_path}...'))
        
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                items_data = json.load(f)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading JSON: {str(e)}'))
            return

        if not isinstance(items_data, list):
            self.stdout.write(self.style.ERROR('JSON data must be a list of items.'))
            return

        # Get or create an executive user for auditing
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')

        # Get default category
        category = Category.objects.first()
        if not category:
            # Create a default category if none exists
            category = Category.objects.create(
                name='General',
                code='GEN',
                created_by=admin_user,
                updated_by=admin_user
            )

        self.stdout.write(f'Using category: {category.name} ({category.code})')

        created_count = 0
        updated_count = 0
        
        with transaction.atomic():
            for entry in items_data:
                sku = entry.get('STKCOD')
                name = entry.get('STKDES')
                name2 = entry.get('STKDES2', '')
                unit = entry.get('QUCOD', 'Unit')
                
                if not sku or not name:
                    continue
                
                # Clean data
                sku = str(sku).strip()
                name = str(name).strip()
                name2 = str(name2).strip()
                unit = str(unit).strip()

                # Check if item exists
                item = Item.objects.filter(sku=sku).first()
                
                if item:
                    # Update existing item
                    item.name = name
                    item.name2 = name2
                    item.unit = unit
                    item.express_sku = sku
                    item.updated_by = admin_user
                    item.save()
                    updated_count += 1
                else:
                    # Create new item
                    ItemService.create(
                        sku=sku,
                        name=name,
                        name2=name2,
                        unit=unit,
                        express_sku=sku,
                        category=category,
                        user=admin_user
                    )
                    created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Successfully processed {len(items_data)} items.\n'
            f'Created: {created_count}, Updated: {updated_count}'
        ))
