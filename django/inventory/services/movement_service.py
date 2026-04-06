"""
Inventory Movement Service (Draft Phase)

Handles creating and modifying movement documents during the draft stage.
Enforces draft-only modification rules.
"""

from django.core.exceptions import ValidationError
from inventory.models import InventoryMovement, InventoryMovementItem, InventoryMovementAttachment


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
    def create_movement(*, document_no, type, date, warehouse, user, partner=None, note=''):
        """
        Create a new inventory movement document in Draft status.
        """
        movement = InventoryMovement(
            document_no=document_no,
            type=type,
            date=date,
            warehouse=warehouse,
            partner=partner,
            note=note,
            created_by=user,
            status=InventoryMovement.Status.DRAFT
        )
        movement.full_clean()
        movement.save()
        return movement

    @staticmethod
    def update_header(movement, *, user, **fields):
        """
        Update header fields of a draft movement.
        """
        MovementService._ensure_draft(movement)
        
        allowed_fields = {'date', 'warehouse', 'partner', 'note'}
        for field, value in fields.items():
            if field in allowed_fields:
                setattr(movement, field, value)
        
        movement.updated_by = user
        movement.full_clean()
        movement.save()
        return movement

    @staticmethod
    def add_item(movement, *, item, lot_number, quantity, user, unit_cost=None, mfg_date=None, exp_date=None, note=''):
        """
        Add an item line to a draft movement.
        """
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
        
        # Log update on movement
        movement.updated_by = user
        movement.save()
        return item_line

    @staticmethod
    def update_item(item_line, *, user, **fields):
        """
        Update an item line in a draft movement.
        """
        MovementService._ensure_draft(item_line.movement)
        
        allowed_fields = {'lot_number', 'quantity', 'unit_cost', 'mfg_date', 'exp_date', 'note'}
        for field, value in fields.items():
            if field in allowed_fields:
                if field == 'lot_number' and value:
                    value = value.strip().upper()
                setattr(item_line, field, value)
        
        item_line.full_clean()
        item_line.save()
        
        # Log update on movement
        item_line.movement.updated_by = user
        item_line.movement.save()
        return item_line

    @staticmethod
    def remove_item(item_line, *, user):
        """
        Remove an item line from a draft movement.
        """
        MovementService._ensure_draft(item_line.movement)
        
        movement = item_line.movement
        item_line.delete()
        
        # Log update on movement
        movement.updated_by = user
        movement.save()

    @staticmethod
    def add_attachment(movement, *, document_file, user, note=''):
        """
        Add a file attachment to a draft movement.
        """
        MovementService._ensure_draft(movement)
        
        attachment = InventoryMovementAttachment(
            movement=movement,
            document_file=document_file,
            note=note,
            created_by=user
        )
        attachment.full_clean()
        attachment.save()
        
        # Log update on movement
        movement.updated_by = user
        movement.save()
        return attachment

    @staticmethod
    def remove_attachment(attachment, *, user):
        """
        Remove an attachment from a draft movement.
        """
        MovementService._ensure_draft(attachment.movement)
        
        movement = attachment.movement
        attachment.delete(user=user) # Soft delete
        
        # Log update on movement
        movement.updated_by = user
        movement.save()

    @staticmethod
    def delete_draft(movement, *, user):
        """
        Soft-delete the entire movement draft.
        """
        MovementService._ensure_draft(movement)
        movement.delete(user=user) # Soft delete
