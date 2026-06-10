"""
Inventory Movement Service

Handles the full lifecycle of inventory movement documents.
Includes draft operations, completion logic (stock updates), and reversion.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from inventory.models import InventoryMovement, InventoryMovementItem, InventoryMovementAttachment, Stock, StockCard


class MovementService:

    @staticmethod
    def _ensure_draft(movement):
        """Internal helper to ensure the document is in draft state."""
        if movement.status != InventoryMovement.Status.DRAFT:
            raise ValidationError(
                f"Cannot modify document '{movement.document_no}' because "
                f"it is currently in '{movement.get_status_display()}' status."
            )

    @staticmethod
    def _ensure_completed(movement):
        """Internal helper to ensure the document is in completed state."""
        if movement.status != InventoryMovement.Status.COMPLETED:
            raise ValidationError(
                f"Cannot revert document '{movement.document_no}' because "
                f"it is currently in '{movement.get_status_display()}' status."
            )

    @staticmethod
    def create_movement(*, document_no, type, date, warehouse, user, partner=None, recipient='', note=''):
        """Create a new inventory movement document in Draft status."""
        movement = InventoryMovement(
            document_no=document_no,
            type=type,
            date=date,
            warehouse=warehouse,
            partner=partner,
            recipient=recipient,
            note=note,
            created_by=user,
            status=InventoryMovement.Status.DRAFT
        )
        movement.full_clean()
        movement.save()
        return movement

    @staticmethod
    def update_header(movement, *, user, **fields):
        """Update header fields of a draft movement."""
        MovementService._ensure_draft(movement)
        allowed_fields = {'date', 'warehouse', 'partner', 'recipient', 'note'}
        for field, value in fields.items():
            if field in allowed_fields:
                setattr(movement, field, value)
        movement.updated_by = user
        movement.full_clean()
        movement.save()
        return movement


    @staticmethod
    def add_item(movement, *, item, lot_number, quantity, user, unit_cost=None, mfg_date=None, exp_date=None, arrival_item=None, note=''):
        """Add an item line to a draft movement."""
        MovementService._ensure_draft(movement)
        
        cleaned_lot = lot_number.strip().upper() if lot_number else ''
        
        if movement.items.filter(item=item, lot_number=cleaned_lot).exists():
            raise ValidationError("Item and lot number already exists in movement")
            
        item_line = InventoryMovementItem(
            movement=movement,
            item=item,
            lot_number=cleaned_lot,
            quantity=quantity,
            unit_cost=unit_cost,
            mfg_date=mfg_date,
            exp_date=exp_date,
            arrival_item=arrival_item,
            note=note
        )
        item_line.full_clean()
        item_line.save()
        movement.updated_by = user
        movement.save()
        return item_line

    @staticmethod
    def update_item(item_line, *, user, **fields):
        """Update an item line in a draft movement."""
        MovementService._ensure_draft(item_line.movement)
        allowed_fields = {'lot_number', 'quantity', 'unit_cost', 'mfg_date', 'exp_date', 'note', 'item'}
        
        new_lot = item_line.lot_number
        new_item = item_line.item
        
        for field, value in fields.items():
            if field in allowed_fields:
                if field == 'lot_number' and value:
                    value = value.strip().upper()
                    new_lot = value
                if field == 'item' and value:
                    new_item = value
                setattr(item_line, field, value)
                
        # Check for duplicates excluding self
        if item_line.movement.items.filter(item=new_item, lot_number=new_lot).exclude(pk=item_line.pk).exists():
            raise ValidationError("Item and lot number already exists in movement")
            
        item_line.full_clean()
        item_line.save()
        item_line.movement.updated_by = user
        item_line.movement.save()
        return item_line

    @staticmethod
    def remove_item(item_line, *, user):
        """Remove an item line from a draft movement."""
        MovementService._ensure_draft(item_line.movement)
        movement = item_line.movement
        item_line.delete()
        movement.updated_by = user
        movement.save()

    @staticmethod
    def add_attachment(movement, *, document_file, user, note=''):
        """Add a file attachment to a draft movement."""
        MovementService._ensure_draft(movement)
        attachment = InventoryMovementAttachment(
            movement=movement,
            document_file=document_file,
            note=note,
            created_by=user
        )
        attachment.full_clean()
        attachment.save()
        movement.updated_by = user
        movement.save()
        return attachment

    @staticmethod
    def remove_attachment(attachment, *, user):
        """Remove an attachment from a draft movement."""
        MovementService._ensure_draft(attachment.movement)
        movement = attachment.movement
        attachment.delete(user=user)
        movement.updated_by = user
        movement.save()

    @staticmethod
    @transaction.atomic
    def delete_draft(movement, *, user):
        """Soft-delete the entire movement draft."""
        MovementService._ensure_draft(movement)
        
        # Restore linked Sales Order status to CONFIRMED if OUTBOUND and status is PROCESSING
        if (movement.reference_type == InventoryMovement.ReferenceType.SALES_ORDER 
            and movement.type == InventoryMovement.MovementType.OUTBOUND):
            from sales.models import SalesOrder
            try:
                sales_order = SalesOrder.objects.get(document_no=movement.reference_no, is_deleted=False)
                if sales_order.status == SalesOrder.Status.PROCESSING:
                    sales_order.status = SalesOrder.Status.CONFIRMED
                    sales_order.updated_by = user
                    sales_order.save(update_fields=['status', 'updated_by', 'updated_at', 'version'])
            except SalesOrder.DoesNotExist:
                pass
                
        movement.delete(user=user)

    @staticmethod
    def list_deleted():
        """Retrieve all soft-deleted movements."""
        return InventoryMovement.objects.select_related('warehouse', 'partner').filter(is_deleted=True).order_by('-deleted_at')

    @staticmethod
    def restore(movement, *, user):
        """Restore a soft-deleted movement."""
        if not movement.is_deleted:
            return movement
        movement.restore()
        movement.updated_by = user
        movement.save()
        return movement

    @staticmethod
    @transaction.atomic
    def create_outbound_from_reservations(sales_order, user):
        """
        Generates a Draft Outbound Inventory Movement from the active StockReservation records
        of the given SalesOrder. Grouped by Warehouse.
        """
        from inventory.models import StockReservation, InventoryMovement, InventoryMovementItem
        from django.utils import timezone
        
        # 1. Query active reservations for the Sales Order
        reservations = StockReservation.objects.filter(
            reference_no=str(sales_order.id),
            reference_type=StockReservation.ReferenceType.SALES_ORDER,
            is_deleted=False,
            status=StockReservation.ReservationStatus.RESERVED
        ).select_related('stock__warehouse', 'sales_item__item')

        if not reservations.exists():
            raise ValidationError(
                f"Cannot release Sales Order '{sales_order.document_no}' to warehouse because it has no active stock reservations."
            )

        # 2. Group reservations by warehouse
        warehouse_groups = {}
        for res in reservations:
            wh = res.stock.warehouse
            if wh not in warehouse_groups:
                warehouse_groups[wh] = []
            warehouse_groups[wh].append(res)

        created_movements = []

        # 3. Create one outbound InventoryMovement per warehouse
        for warehouse, wh_reservations in warehouse_groups.items():
            doc_no = f"OUT-{sales_order.document_no}-{warehouse.code}".upper()
            
            # Avoid creating duplicates if the button was clicked multiple times or already exists
            if InventoryMovement.objects.filter(document_no=doc_no, is_deleted=False).exists():
                movement = InventoryMovement.objects.filter(document_no=doc_no, is_deleted=False).first()
                created_movements.append(movement)
                continue

            movement = InventoryMovement.objects.create(
                document_no=doc_no,
                type=InventoryMovement.MovementType.OUTBOUND,
                status=InventoryMovement.Status.DRAFT,
                date=timezone.now().date(),
                warehouse=warehouse,
                partner=sales_order.partner,
                reference_type=InventoryMovement.ReferenceType.SALES_ORDER,
                reference_no=sales_order.document_no,
                created_by=user
            )

            # Create items under this movement for each reservation
            for res in wh_reservations:
                InventoryMovementItem.objects.create(
                    movement=movement,
                    item=res.stock.item,
                    lot_number=res.stock.lot_number,
                    quantity=res.quantity,
                    mfg_date=res.stock.mfg_date,
                    exp_date=res.stock.exp_date,
                    note=f"Transferred from Sales Order reservation hold."
                )
            
            created_movements.append(movement)

        return created_movements

    # --- Completion & Reversion Logic ---

    @staticmethod
    def complete_movement(movement, *, user):
        """
        Finalize a movement: Update Stock balances and generate StockCard audit ledger.
        Locked by transaction.atomic with row-level locking manually.
        """
        MovementService._ensure_draft(movement)
        items = movement.items.all()
        if not items.exists():
            raise ValidationError(f"Cannot complete movement '{movement.document_no}' without any item lines.")

        with transaction.atomic():
            # Process each line item
            for item_line in items:
                # 1. Lock and get/create Stock for (warehouse, item, lot_number)
                stock, created = Stock.objects.select_for_update().get_or_create(
                    warehouse=movement.warehouse,
                    item=item_line.item,
                    lot_number=item_line.lot_number,
                    defaults={
                        'created_by': user,
                        'mfg_date': item_line.mfg_date,
                        'exp_date': item_line.exp_date,
                        'balance': 0
                    }
                )

                # 2. Calculate balance change
                # Inbound = Add, Outbound = Subtract
                change = item_line.quantity
                if movement.type == InventoryMovement.MovementType.OUTBOUND:
                    change = -change
                
                # 3. Update stock balance
                stock.balance += change
                stock.updated_by = user
                stock.save()

                # 4. Create StockCard entry
                StockCard.objects.create(
                    stock=stock,
                    warehouse=movement.warehouse,
                    item=item_line.item,
                    lot_number=item_line.lot_number,
                    movement_item=item_line,
                    quantity=item_line.quantity,
                    type=StockCard.StockCardType.IN if movement.type == InventoryMovement.MovementType.INBOUND else StockCard.StockCardType.OUT,
                    note=f"[COMPLETION]: Movement {movement.document_no}",
                    created_by=user
                )

            # 5. Mark movement as completed
            movement.status = InventoryMovement.Status.COMPLETED
            movement.updated_by = user
            movement.save()

            # 5b. Update linked Sales Order if reference matches
            if (movement.reference_type == InventoryMovement.ReferenceType.SALES_ORDER 
                and movement.type == InventoryMovement.MovementType.OUTBOUND):
                from sales.models import SalesOrder, SalesOrderItem
                from inventory.models import StockReservation
                from inventory.services import ReservationService

                try:
                    sales_order = SalesOrder.objects.get(document_no=movement.reference_no, is_deleted=False)
                except SalesOrder.DoesNotExist:
                    sales_order = None

                if sales_order:
                    # Update each sales order item and release reservations
                    for item_line in items:
                        sales_item = SalesOrderItem.objects.filter(
                            order=sales_order,
                            item=item_line.item
                        ).first()
                        if sales_item:
                            sales_item.fulfilled_qty += item_line.quantity
                            if sales_item.fulfilled_qty >= sales_item.requested_qty:
                                sales_item.status = SalesOrderItem.Status.SHIPPED
                            else:
                                sales_item.status = SalesOrderItem.Status.PARTIAL
                            sales_item.save(update_fields=['fulfilled_qty', 'status'])

                        # Complete corresponding reservations matching this warehouse, item, and lot
                        matching_reservations = StockReservation.objects.filter(
                            reference_no=str(sales_order.id),
                            reference_type=StockReservation.ReferenceType.SALES_ORDER,
                            stock__item=item_line.item,
                            stock__lot_number=item_line.lot_number,
                            stock__warehouse=movement.warehouse,
                            is_deleted=False,
                            status=StockReservation.ReservationStatus.RESERVED
                        )
                        for res in matching_reservations:
                            ReservationService.complete(res, user=user)

                    # Update overall sales order status to SHIPPED if all items are fully shipped or cancelled
                    total_items_count = sales_order.items.count()
                    shipped_or_cancelled_count = sales_order.items.filter(
                        status__in=[SalesOrderItem.Status.SHIPPED, SalesOrderItem.Status.CANCELLED]
                    ).count()
                    if shipped_or_cancelled_count == total_items_count:
                        sales_order.status = SalesOrder.Status.SHIPPED
                        sales_order.save(update_fields=['status'])

    @staticmethod
    def revert_to_draft(movement, *, user):
        """
        Revert a completed movement back to Draft.
        Inverts stock changes and adds reversal entries to StockCard.
        Only allowed if stock level remains safe.
        """
        MovementService._ensure_completed(movement)
        items = movement.items.all()

        with transaction.atomic():
            for item_line in items:
                # 1. Lock Stock record
                try:
                    stock = Stock.objects.select_for_update().get(
                        warehouse=movement.warehouse,
                        item=item_line.item,
                        lot_number=item_line.lot_number
                    )
                except Stock.DoesNotExist:
                    raise ValidationError(f"Critical Error: Stock record for {item_line.lot_number} missing during reversal.")

                # 2. Calculate inversion change
                # Reversed Inbound = Subtract, Reversed Outbound = Add
                rev_change = item_line.quantity
                if movement.type == InventoryMovement.MovementType.INBOUND:
                    rev_change = -rev_change

                # 4. Update Stock balance
                stock.balance += rev_change
                stock.updated_by = user
                stock.save()

                # 5. Create Reversal StockCard entry
                # Inverted Inbound -> Records as OUT
                # Inverted Outbound -> Records as IN
                StockCard.objects.create(
                    stock=stock,
                    warehouse=movement.warehouse,
                    item=item_line.item,
                    lot_number=item_line.lot_number,
                    movement_item=item_line,
                    quantity=item_line.quantity,
                    type=StockCard.StockCardType.OUT if movement.type == InventoryMovement.MovementType.INBOUND else StockCard.StockCardType.IN,
                    note=f"[REVERSION]: Reversal of Movement {movement.document_no}",
                    created_by=user
                )

            # 6. Mark movement as Draft
            movement.status = InventoryMovement.Status.DRAFT
            movement.updated_by = user
            movement.save()

            # 6b. Revert linked Sales Order transitions & restore reservations
            if (movement.reference_type == InventoryMovement.ReferenceType.SALES_ORDER 
                and movement.type == InventoryMovement.MovementType.OUTBOUND):
                from sales.models import SalesOrder, SalesOrderItem
                from inventory.models import StockReservation
                from inventory.services import ReservationService

                try:
                    sales_order = SalesOrder.objects.get(document_no=movement.reference_no, is_deleted=False)
                except SalesOrder.DoesNotExist:
                    sales_order = None

                if sales_order:
                    for item_line in items:
                        sales_item = SalesOrderItem.objects.filter(
                            order=sales_order,
                            item=item_line.item
                        ).first()
                        if sales_item:
                            sales_item.fulfilled_qty = max(0, sales_item.fulfilled_qty - item_line.quantity)
                            if sales_item.fulfilled_qty == 0:
                                sales_item.status = SalesOrderItem.Status.ALLOCATED
                            else:
                                sales_item.status = SalesOrderItem.Status.PARTIAL
                            sales_item.save(update_fields=['fulfilled_qty', 'status'])

                        # Re-create or reactivate the reservation hold for the item lot
                        stock = Stock.objects.filter(
                            warehouse=movement.warehouse,
                            item=item_line.item,
                            lot_number=item_line.lot_number
                        ).first()
                        if stock:
                            res = StockReservation.objects.filter(
                                reference_no=str(sales_order.id),
                                reference_type=StockReservation.ReferenceType.SALES_ORDER,
                                stock=stock,
                                status=StockReservation.ReservationStatus.COMPLETED,
                                is_deleted=False
                            ).first()
                            
                            if res:
                                res.status = StockReservation.ReservationStatus.RESERVED
                                if user:
                                    res.updated_by = user
                                res.save()
                                ReservationService._sync_stock_reserved_qty(stock)
                            else:
                                res = ReservationService.reserve(
                                    stock=stock,
                                    quantity=item_line.quantity,
                                    reference_no=str(sales_order.id),
                                    reference_type=StockReservation.ReferenceType.SALES_ORDER,
                                    sales_item=sales_item,
                                    note="Restored during inventory movement reversion to draft.",
                                    created_by=user
                                )
                                
                                # Link to SalesAllocation to maintain strict database integrity
                                from sales.models import SalesAllocation
                                alloc = SalesAllocation.objects.filter(
                                    order_item=sales_item,
                                    source_type=SalesAllocation.SourceType.STOCK,
                                    physical_reservation__isnull=True,
                                    is_deleted=False
                                ).first()
                                if alloc:
                                    alloc.physical_reservation = res
                                    alloc.save(update_fields=['physical_reservation'])
                                else:
                                    SalesAllocation.objects.create(
                                        order_item=sales_item,
                                        source_type=SalesAllocation.SourceType.STOCK,
                                        physical_reservation=res,
                                        quantity=item_line.quantity,
                                        is_manual=False,
                                        created_by=user
                                    )

                    # Demote SalesOrder status back from SHIPPED to PROCESSING
                    if sales_order.status == SalesOrder.Status.SHIPPED:
                        sales_order.status = SalesOrder.Status.PROCESSING
                        sales_order.save(update_fields=['status'])
