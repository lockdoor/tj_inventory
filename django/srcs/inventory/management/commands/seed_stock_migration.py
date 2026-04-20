import json
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from django.conf import settings


from catalog.models import Item
from inventory.models import Warehouse, InventoryMovement
from inventory.services.movement_service import MovementService

class Command(BaseCommand):
    help = 'Seed stock movement data from migration JSON'

    def handle(self, *args, **options):
        json_path = os.path.join(settings.BASE_DIR, '..', 'private', 'data', 'stock_migration.json')

        
        if not os.path.exists(json_path):
            self.stdout.write(self.style.ERROR(f"File not found: {json_path}"))
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 1. Resolve Admin User
        user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR("No user found in database. Create a superuser first."))
            return

        self.stdout.write(self.style.NOTICE(f"Starting migration seed of {len(data)} records..."))

        movements_count = 0
        errors = []

        try:
            with transaction.atomic():
                for index, entry in enumerate(data):
                    sku = entry.get('sku')
                    wh_code = entry.get('warehouse')
                    move_type = entry.get('type')
                    quantity = entry.get('quantity', 0)
                    date_str = entry.get('date')
                    exp_date_str = entry.get('exp_date')
                    doc_no = entry.get('doc_no')
                    partner_name = entry.get('partner')
                    note = entry.get('note', '')

                    # 1. Resolve Item
                    try:
                        item = Item.objects.get(sku=sku)
                    except Item.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f"Row {index}: SKU {sku} not found."))
                        raise ValueError(f"SKU {sku} missing from Catalog.")

                    # 2. Resolve Warehouse
                    try:
                        warehouse = Warehouse.objects.get(code=wh_code)
                    except Warehouse.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f"Row {index}: Warehouse {wh_code} not found."))
                        raise ValueError(f"Warehouse {wh_code} missing from database.")

                    # 3. Preparation
                    m_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.now().date()
                    exp_date = datetime.strptime(exp_date_str, '%Y-%m-%d').date() if exp_date_str else None
                    
                    # Grouping Logic: For this migration, we treat each entry as a distinct document 
                    # unless they share a doc_no and are consecutive (optional complexity).
                    # We'll stick to 1-to-1 for reliability of the ledger.
                    if not doc_no:
                        doc_no = f"MIG-{wh_code}-{m_date.strftime('%Y%m%d')}-{index:04d}"

                    # 4. Create Movement
                    movement = MovementService.create_movement(
                        document_no=doc_no,
                        type=move_type,
                        date=m_date,
                        warehouse=warehouse,
                        user=user,
                        recipient=partner_name if move_type == 'outbound' else '',
                        note=note
                    )

                    # 5. Add Item Line
                    # Unique Lot Name Logic: LOT-{sku}-{exp_date}
                    lot_name = f"LOT-{sku}-{exp_date_str if exp_date_str else 'NOEXP'}"
                    
                    MovementService.add_item(
                        movement,
                        item=item,
                        lot_number=lot_name,
                        quantity=quantity,
                        user=user,
                        exp_date=exp_date,
                        note=note
                    )

                    # 6. Complete Movement (Generates Stock & StockCard)
                    MovementService.complete_movement(movement, user=user)
                    movements_count += 1

            self.stdout.write(self.style.SUCCESS(f"Successfully migrated {movements_count} movements."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Migration failed: {str(e)}"))
            # Transaction rolls back automatically
