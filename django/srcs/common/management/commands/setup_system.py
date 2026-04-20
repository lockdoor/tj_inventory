import os
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.contrib.auth.models import User
from django.db import transaction

# Core Models for detection and cleaning
from catalog.models import Category, Item, ItemImage
from partners.models import Partner
from inventory.models import (
    Warehouse, Stock, InventoryMovement, 
    InventoryMovementItem, InventoryMovementAttachment, StockCard
)

class Command(BaseCommand):
    help = 'Initialize the entire system from scratch with safety guard and forced cleanup.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force execution (DANGEROUS: will CLEAN all existing data before seeding)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('\n' + '='*40))
        self.stdout.write(self.style.NOTICE(' SYSTEM INITIALIZATION & SETUP '))
        self.stdout.write(self.style.NOTICE('='*40))

        # 1. Safety Guard Check
        self.stdout.write('\n[Step 1] Checking database status...')
        
        data_checks = {
            'Items': Item.objects.exists(),
            'Partners': Partner.objects.exists(),
            'Warehouses': Warehouse.objects.exists(),
        }

        has_existing_data = any(data_checks.values())

        if has_existing_data:
            if not options['force']:
                self.stdout.write(self.style.WARNING('\n⚠️ SAFETY WARNING ⚠️'))
                self.stdout.write(self.style.WARNING('Existing business data detected:'))
                for model, exists in data_checks.items():
                    if exists:
                        self.stdout.write(self.style.WARNING(f' - {model}: Data exists'))
                
                self.stdout.write('')
                raise CommandError(
                    'Aborting setup to prevent data duplication/corruption.\n'
                    'If you intend to clean and re-seed, use the --force flag.'
                )
            else:
                self.stdout.write(self.style.SUCCESS('\n--force flag detected.'))
                self.clean_existing_data()
        else:
            self.stdout.write(self.style.SUCCESS(' ✓ Database is clean. Proceeding.'))

        # 2. Superuser Initialization
        self.stdout.write(self.style.NOTICE('\n[Step 2] Initializing Superuser...'))
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            self.stdout.write('   Creating superuser "admin"...')
            username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
            email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
            password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')
            
            User.objects.create_superuser(username, email, password)
            self.stdout.write(self.style.SUCCESS(f'   ✓ Created superuser "{username}"'))
        else:
            self.stdout.write(f'   ✓ Superuser "{admin_user.username}" already exists.')

        # 3. Run Sequential Seeders
        self.stdout.write(self.style.NOTICE('\n[Step 3] Running module seeders...'))
        
        seeders = [
            ('seed_groups', 'Roles & Permissions (common)'),
            # ('seed_catalog', 'Product Categories (catalog)'),
            ('seed_items_real', 'Real Product Items (catalog)'),
            # ('seed_partners', 'Suppliers & Customers (partners)'),
            ('seed_warehouses_real', 'Warehouse Structure (inventory)'),
            ('seed_stock_migration', 'Stock Migration (inventory)'),
            # ('seed_inventory_data', 'Sample stock records (inventory)'),
        ]

        for cmd, description in seeders:
            self.stdout.write(self.style.NOTICE(f'\n→ Executing {cmd} ({description})...'))
            # Exceptions will propagate and stop the script immediately
            call_command(cmd)

        self.stdout.write(self.style.NOTICE('\n' + '='*40))
        self.stdout.write(self.style.SUCCESS(' SETUP FINISHED SUCCESSFULLY '))
        self.stdout.write(self.style.NOTICE('='*40 + '\n'))

    def clean_existing_data(self):
        """Delete all records from core models in correct dependency order."""
        self.stdout.write(self.style.NOTICE('   Starting recursive data cleanup...'))
        with transaction.atomic():
            # 1. Inventory & Movements (Highest dependency)
            models_to_clean = [
                (InventoryMovementAttachment, "Movement Attachments"),
                (InventoryMovementItem, "Movement Items"),
                (InventoryMovement, "Movements"),
                (StockCard, "Stock Card entries"),
                (Stock, "Stock balances"),
                (Warehouse, "Warehouses"),
                (Partner, "Partners"),
            ]
            
            for model_class, name in models_to_clean:
                count = model_class.objects.all().delete()[0]
                if count or model_class.objects.all().exists():
                    self.stdout.write(f'   - Cleaned {count} {name}')

            # 3. Catalog (Category has self-referential PROTECT foreign key)
            ItemImage.objects.all().delete()
            Item.objects.all().delete()
            
            # Null out parents to avoid ProtectedError on self-referential FK
            Category.objects.all().update(parent=None)
            Category.objects.all().delete()
            
            self.stdout.write(self.style.SUCCESS('   ✓ Database cleanup complete.'))
