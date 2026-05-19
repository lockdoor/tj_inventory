from django.db import transaction
from django.core.exceptions import ValidationError
from procurement.models import Arrival, ArrivalItem


class ArrivalService:
    """
    Business logic for Arrival operations.
    """

    @staticmethod
    def get_active_queryset():
        return Arrival.objects.filter(is_deleted=False).select_related('partner', 'warehouse', 'purchase_order')

    @staticmethod
    @transaction.atomic
    def create(*, document_no, partner, warehouse, expected_date, user, purchase_order=None, note='', items=None):
        """
        Create a new Arrival document with items.
        """
        arrival = Arrival(
            document_no=document_no,
            purchase_order=purchase_order,
            partner=partner,
            warehouse=warehouse,
            expected_date=expected_date,
            note=note,
            created_by=user,
            status=Arrival.Status.SCHEDULED
        )
        arrival.full_clean()
        arrival.save()

        if items:
            for item_data in items:
                ArrivalItem.objects.create(
                    arrival=arrival,
                    item=item_data['item'],
                    po_item=item_data.get('po_item'),
                    packaging=item_data.get('packaging'),
                    expected_qty=item_data['expected_qty'],
                    received_qty=item_data.get('received_qty', 0)
                )
        
        return arrival

    @staticmethod
    @transaction.atomic
    def update(arrival, *, user, items_data=None, **fields):
        """
        Update an Arrival document and its items.
        """
        if arrival.status == Arrival.Status.RECEIVED:
            raise ValidationError("Cannot update an arrival that has already been received.")

        # Update header fields
        for field, value in fields.items():
            setattr(arrival, field, value)
        
        arrival.updated_by = user
        arrival.full_clean()
        arrival.save()

        if items_data is not None:
            ArrivalService.sync_items(arrival, items_data)

        return arrival

    @staticmethod
    @transaction.atomic
    def delete(arrival, *, user):
        """
        Delete an Arrival document.
        - Cannot delete if there are active (non-deleted) inventory movements referencing it.
        - Will hard-delete any soft-deleted inventory movements referencing it.
        """
        from inventory.models import InventoryMovement
        from django.core.exceptions import ValidationError

        movements = InventoryMovement.objects.filter(
            reference_type=InventoryMovement.ReferenceType.STOCK_ARRIVAL,
            reference_no=arrival.document_no
        )

        # 1. Check for active movements
        if movements.filter(is_deleted=False).exists():
            raise ValidationError("Cannot delete an arrival that has active inventory movements referencing it.")

        # 2. Hard-delete soft-deleted movements
        soft_deleted_movements = movements.filter(is_deleted=True)
        for mov in soft_deleted_movements:
            mov.hard_delete()

        # 3. Soft-delete the arrival
        arrival.delete(user=user)
        return arrival

    @staticmethod
    def sync_items(arrival, items_data):
        """
        Sync ArrivalItems based on formset data.
        """
        existing_items = {item.id: item for item in arrival.items.all()}
        
        for item_info in items_data:
            if not item_info:
                continue

            item_id = item_info.get('id')
            is_delete = item_info.get('DELETE', False)
            
            if is_delete:
                if item_id and item_id in existing_items:
                    existing_items[item_id].delete()
                continue
            
            # Must have an item selected to create/update
            if not item_info.get('item'):
                continue
                
            if item_id and item_id in existing_items:
                # Update existing
                item = existing_items[item_id]
                item.item = item_info['item']
                item.packaging = item_info.get('packaging')
                item.expected_qty = item_info['expected_qty']
                item.save()
            else:
                # Create new
                ArrivalItem.objects.create(
                    arrival=arrival,
                    item=item_info['item'],
                    po_item=item_info.get('po_item'),
                    packaging=item_info.get('packaging'),
                    expected_qty=item_info['expected_qty'],
                    received_qty=0
                )

    @staticmethod
    @transaction.atomic
    def initiate_receiving(arrival, user):
        """
        Creates or restores a DRAFT InventoryMovement based on the Arrival.
        Bridges Procurement and Inventory modules.
        """
        from inventory.services.movement_service import MovementService
        from inventory.models import InventoryMovement
        
        if arrival.status in [Arrival.Status.RECEIVING, Arrival.Status.RECEIVED]:
             raise ValidationError("This arrival is already in progress or completed.")

        # Check if there is a soft-deleted movement for this arrival
        existing_movement = InventoryMovement.objects.filter(
            reference_type=InventoryMovement.ReferenceType.STOCK_ARRIVAL,
            reference_no=arrival.document_no,
            is_deleted=True
        ).first()

        if existing_movement:
            movement = MovementService.restore(existing_movement, user=user)
            # Clear out old movement items to ensure fresh sync with current arrival items
            movement.items.all().delete()
        else:
            # 1. Create the Movement Header
            movement = MovementService.create_movement(
                document_no=f"RCV-{arrival.document_no}",
                type=InventoryMovement.MovementType.INBOUND,
                date=arrival.expected_date,
                warehouse=arrival.warehouse,
                user=user,
                partner=arrival.partner,
                note=f"Receiving for Arrival {arrival.document_no}. PO: {arrival.purchase_order.document_no if arrival.purchase_order else 'N/A'}"
            )
            movement.reference_type = InventoryMovement.ReferenceType.STOCK_ARRIVAL
            movement.reference_no = arrival.document_no
            movement.save()

        # 2. Copy items
        for arrival_item in arrival.items.all():
            qty = arrival_item.expected_qty
            if arrival_item.packaging and arrival_item.packaging.quantity:
                qty = qty * arrival_item.packaging.quantity

            unit_cost = arrival_item.po_item.unit_cost if arrival_item.po_item else None
            if unit_cost is not None and arrival_item.packaging and arrival_item.packaging.quantity:
                unit_cost = unit_cost / arrival_item.packaging.quantity

            MovementService.add_item(
                movement,
                item=arrival_item.item,
                lot_number=f"PENDING-{arrival_item.id}", # Placeholder: Staff must update this during physical receiving
                quantity=qty,
                user=user,
                unit_cost=unit_cost,
                arrival_item=arrival_item,
                note=f"[AUTO-GENERATED] Please update Lot Number and Expiry Date. Original Note: {arrival_item.arrival.note}"
            )

        # 3. Update Arrival Status
        arrival.status = Arrival.Status.RECEIVING
        arrival.updated_by = user
        arrival.save()

        return movement

    @staticmethod
    @transaction.atomic
    def cancel_receiving(arrival, user):
        """
        Reverts an Arrival in RECEIVING status back to SCHEDULED.
        Soft-deletes the linked draft InventoryMovement.
        """
        if arrival.status != Arrival.Status.RECEIVING:
            raise ValidationError("Only arrivals in RECEIVING status can be cancelled back to SCHEDULED.")
        
        from inventory.models import InventoryMovement
        from inventory.services.movement_service import MovementService
        
        movement = InventoryMovement.objects.filter(
            reference_type=InventoryMovement.ReferenceType.STOCK_ARRIVAL,
            reference_no=arrival.document_no,
            is_deleted=False,
            status=InventoryMovement.Status.DRAFT
        ).first()
        
        if movement:
            MovementService.delete_draft(movement, user=user)
            
        arrival.status = Arrival.Status.SCHEDULED
        arrival.updated_by = user
        arrival.save()
        return arrival

    @staticmethod
    def mark_received(arrival, *, user, received_items=None):
        """
        Mark arrival as received. 
        If received_items is provided, update received_qty for each line.
        """
        with transaction.atomic():
            if received_items:
                for line_id, qty in received_items.items():
                    item = ArrivalItem.objects.get(id=line_id, arrival=arrival)
                    item.received_qty = qty
                    item.save()

            arrival.status = Arrival.Status.RECEIVED
            arrival.updated_by = user
            arrival.save()
        
        return arrival

    @staticmethod
    @transaction.atomic
    def finalize_from_movement(movement, user):
        """
        Updates Arrival data based on a COMPLETED InventoryMovement.
        """
        if movement.status != movement.Status.COMPLETED:
            return
            
        if movement.reference_type != movement.ReferenceType.STOCK_ARRIVAL:
            return
            
        try:
            arrival = Arrival.objects.get(document_no=movement.reference_no, is_deleted=False)
        except Arrival.DoesNotExist:
            return

        # Determine overall status
        from inventory.models import InventoryMovement
        linked_movements = InventoryMovement.objects.filter(
            reference_type=InventoryMovement.ReferenceType.STOCK_ARRIVAL,
            reference_no=arrival.document_no
        )
        
        has_draft = linked_movements.filter(status='draft').exists()
        has_completed = linked_movements.filter(status='completed').exists()
        
        if has_completed and not has_draft:
            arrival.status = Arrival.Status.RECEIVED
        elif has_draft or has_completed:
            arrival.status = Arrival.Status.RECEIVING
        else:
            arrival.status = Arrival.Status.SCHEDULED

        arrival.updated_by = user
        
        # Update received quantities for items by summing all completed movements
        from inventory.models import InventoryMovementItem
        from django.db.models import Sum
        
        for arrival_item in arrival.items.all():
            total_received_pieces = InventoryMovementItem.objects.filter(
                arrival_item=arrival_item,
                movement__status='completed' # status is a string choice
            ).aggregate(total=Sum('quantity'))['total'] or 0

            if arrival_item.packaging and arrival_item.packaging.quantity:
                arrival_item.received_qty = total_received_pieces / arrival_item.packaging.quantity
            else:
                arrival_item.received_qty = total_received_pieces
            arrival_item.save()
                
        arrival.save()
        return arrival

    @staticmethod
    def soft_delete(arrival, *, user):
        """Soft-delete the arrival."""
        if arrival.status == Arrival.Status.RECEIVED:
            raise ValidationError("Cannot delete an arrival that has already been received.")
        
        arrival.is_deleted = True
        arrival.updated_by = user
        arrival.save()
        return arrival
