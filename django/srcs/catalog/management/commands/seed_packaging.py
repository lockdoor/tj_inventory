from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from catalog.models import Item, ItemPackaging
from catalog.services import ItemPackagingService


class Command(BaseCommand):
    help = 'Seed mockup items into the catalog'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding mockup items...')
        
        # Get or create an executive user for auditing
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')

        
        # Get Item from TJ Global exclude TG001_00-3111-14 sampling
        items = Item.objects.filter(sku__startswith='TG001').exclude(sku='TG001_00-3111-14')

        # Create Item Packaging for Carton is 120pcs
        created_count = 0
        for item in items:
            ItemPackagingService.create(
                item=item,
                name='Carton',
                quantity=120,
                user=admin_user
            )
            created_count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {created_count} carton packaging.'))
