from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from catalog.models import Category, Item
from catalog.services.item_service import ItemService
from django.db import transaction

class Command(BaseCommand):
    help = 'Seed mockup items into the catalog'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding mockup items...')
        
        # Get or create an executive user for auditing
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')

        # Get existing categories or create defaults if missing
        categories = {cat.code: cat for cat in Category.objects.filter(is_deleted=False)}
        
        if not categories:
            self.stdout.write(self.style.WARNING('No categories found. Please run seed_catalog first.'))
            return

        mock_data = [
            # Electronics -> Smartphones
            {'sku': 'IPHONE-15-PRO', 'name': 'iPhone 15 Pro 256GB', 'unit': 'Unit', 'cat_code': 'SMART'},
            {'sku': 'SAMSUNG-S24-U', 'name': 'Samsung S24 Ultra', 'unit': 'Unit', 'cat_code': 'SMART'},
            
            # Electronics -> Laptops
            {'sku': 'MACBOOK-M3-14', 'name': 'MacBook Pro 14" M3', 'unit': 'Unit', 'cat_code': 'LAPTOP'},
            {'sku': 'DELL-XPS-15', 'name': 'Dell XPS 15 9530', 'unit': 'Unit', 'cat_code': 'LAPTOP'},

            # Furniture -> Office
            {'sku': 'HERMAN-AERON-B', 'name': 'Herman Miller Aeron (Size B)', 'unit': 'Unit', 'cat_code': 'OFFICE'},
            {'sku': 'UPLIFT-V2-DESK', 'name': 'Uplift V2 Standing Desk', 'unit': 'Unit', 'cat_code': 'OFFICE'},
            
            # Home -> Kitchen
            {'sku': 'NESTLE-NESPRESSO', 'name': 'Nespresso Vertuo Pop', 'unit': 'Unit', 'cat_code': 'KITCHEN'},
        ]

        with transaction.atomic():
            created_count = 0
            for item_data in mock_data:
                cat_code = item_data.pop('cat_code')
                category = categories.get(cat_code)
                
                if category:
                    if not Item.objects.filter(sku=item_data['sku']).exists():
                        ItemService.create(
                            **item_data,
                            category=category,
                            user=admin_user
                        )
                        created_count += 1
                else:
                    # Fallback to first category if code mismatch
                    fallback_cat = list(categories.values())[0]
                    if not Item.objects.filter(sku=item_data['sku']).exists():
                        ItemService.create(
                            **item_data,
                            category=fallback_cat,
                            user=admin_user
                        )
                        created_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {created_count} items.'))
