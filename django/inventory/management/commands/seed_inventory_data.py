"""
Management command: seed_inventory_data

Generates complex inventory history:
- 10 Inventory Movements (IN/OUT)
- 20 StockCard ledger entries
- 10+ Unique LOT numbers
- Transactional completion via MovementService

Usage:
    python manage.py seed_inventory_data
"""

import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

from catalog.models import Item
from inventory.models import Warehouse, InventoryMovement
from inventory.services.movement_service import MovementService

class Command(BaseCommand):
    help = 'Seed complex inventory movements and stockcards.'

    def handle(self, *args, **options):
        # 1. Prerequisites
        user = User.objects.filter(groups__name='executive').first() or User.objects.first()
        items = list(Item.objects.all()[:10])
        warehouses = list(Warehouse.objects.filter(is_deleted=False))

        if not items or not warehouses:
            self.stdout.write(self.style.ERROR('  Required Items or Warehouses missing. Run seed_catalog and seed_warehouses first.'))
            return

        self.stdout.write(self.style.NOTICE(f'\nSeeding Complex Inventory Data as user: {user.username}...'))

        # 2. Sequence Configuration
        # 10 Movements, each with 2 items = 20 StockCards
        num_movements = 10
        
        # We need at least 20 unique lots to satisfy unique=True in Stock 
        # across different potential warehouse combinations in this seed.
        unique_lots = [f"LOT-2026-X{i:03d}" for i in range(1, 21)]
        lot_idx = 0
        
        movements_created = 0
        stockcards_target = 20
        
        try:
            with transaction.atomic():
                for i in range(num_movements):
                    m_type = InventoryMovement.MovementType.INBOUND if i < 7 else InventoryMovement.MovementType.OUTBOUND
                    wh = random.choice(warehouses)
                    doc_no = f"DOC-{m_type[:2].upper()}-{2026}{i:04d}"
                    
                    # Create Movement
                    movement = MovementService.create_movement(
                        document_no=doc_no,
                        type=m_type,
                        date=date.today() - timedelta(days=random.randint(0, 30)),
                        warehouse=wh,
                        user=user,
                        note=f"Seeded movement {i+1} for performance testing."
                    )
                    
                    # Add 2 Items per movement
                    for j in range(2):
                        item = random.choice(items)
                        lot = unique_lots[lot_idx]
                        lot_idx += 1
                        
                        qty = random.randint(10, 100)
                        
                        # If outbound, we don't strictly care about balance for seeding 
                        # as service allows negative balancing
                        MovementService.add_item(
                            movement,
                            item=item,
                            lot_number=lot,
                            quantity=qty,
                            user=user,
                            unit_cost=random.randint(50, 500),
                            mfg_date=date.today() - timedelta(days=random.randint(60, 365)),
                            exp_date=date.today() + timedelta(days=random.randint(60, 365))
                        )
                    
                    # Complete Movement -> Generates StockCards
                    MovementService.complete_movement(movement, user=user)
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Processed {movement.document_no} ({m_type}) with 2 StockCards'))
                    movements_created += 1

            self.stdout.write(self.style.SUCCESS(f'\nDone. Generated {movements_created} movements and exactly {movements_created * 2} StockCard entries.'))
            self.stdout.write(self.style.NOTICE(f'Used {len(lots)} unique lot IDs.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✘ Critical Error: {str(e)}'))
