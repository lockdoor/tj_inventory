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
    def add_item(movement, *, item, lot_number, quantity, user, unit_cost=None, mfg_date=None, exp_date=None, note=''):
        """Add an item line to a draft movement."""
        MovementService._ensure_draft(movement)
        item_line = InventoryMovementItem(
            movement=movement,
            item=item,
            lot_number=lot_number.strip().upper() if lot_number else '',
            quantity=quantity,
            unit_cost=unit_cost,
            mfg_date=mfg_date,
            exp_date=exp_date,
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
        allowed_fields = {'lot_number', 'quantity', 'unit_cost', 'mfg_date', 'exp_date', 'note'}
        for field, value in fields.items():
            if field in allowed_fields:
                if field == 'lot_number' and value:
                    value = value.strip().upper()
                setattr(item_line, field, value)
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
    def delete_draft(movement, *, user):
        """Soft-delete the entire movement draft."""
        MovementService._ensure_draft(movement)
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
