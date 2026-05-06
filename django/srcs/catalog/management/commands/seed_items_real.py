import os
import json
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Group
from django.db import transaction
from django.conf import settings
from catalog.models import Category, Item
from catalog.services.item_service import ItemService

class Command(BaseCommand):
    help = 'Seed real items from migrate/data/migration_config.json'

    def handle(self, *args, **options):
        # Path to the data file
        data_path = os.path.join(settings.BASE_DIR, '..', 'migrate', 'data', 'migration_config.json')
        
        if not os.path.exists(data_path):
            raise CommandError(
                f'Config data not found at: {data_path}\n'
            )

        self.stdout.write(self.style.NOTICE(f'Reading data from {data_path}...'))
        
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading JSON: {str(e)}'))
            return

        if not isinstance(config_data, dict):
            self.stdout.write(self.style.ERROR('JSON data must be a dictionary.'))
            return

        # Get or create an executive user for auditing
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')

        wh_admin_user = User.objects.filter(username='whadmin').first()
        if not wh_admin_user:
            wh_admin_user = User.objects.create_user('whadmin', 'whadmin@example.com', 'tj123456')
            wh_admin_user.groups.add(Group.objects.get(name='warehouse_admin'))

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
            processed_skus = set()
            for group_key, group_data in config_data.items():
                warehouse = group_data.get('warehouse')
                items = group_data.get('items', {})
                
                if not warehouse or not items:
                    continue
                    
                for item_key, item_data in items.items():
                    express_sku = item_data.get('sku')
                    name = item_data.get('name')
                    name2 = item_data.get('name2', '')
                    unit = item_data.get('unit', 'Unit')
                    
                    if not express_sku or not name:
                        continue
                    
                    # Clean data
                    express_sku = str(express_sku).strip()
                    name = str(name).strip()
                    name2 = str(name2).strip()
                    unit = str(unit).strip()
                    
                    # Determine prefix based on warehouse
                    prefix = 'tj' if 'TJ' in warehouse.upper() else 'tg'
                    system_sku = f"{prefix}_{express_sku}"
                    
                    # Skip if we already processed this SKU in this run
                    if system_sku in processed_skus:
                        continue
                    processed_skus.add(system_sku)

                    # Check if item exists
                    item = Item.objects.filter(sku=system_sku).first()
                    
                    if item:
                        # Update existing item
                        item.name = name
                        item.name2 = name2
                        item.unit = unit
                        item.express_sku = express_sku
                        item.updated_by = admin_user
                        item.save()
                        updated_count += 1
                    else:
                        # Create new item
                        ItemService.create(
                            sku=system_sku,
                            name=name,
                            name2=name2,
                            unit=unit,
                            express_sku=express_sku,
                            category=category,
                            user=admin_user
                        )
                        created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Successfully processed unique items.\n'
            f'Created: {created_count}, Updated: {updated_count}'
        ))
