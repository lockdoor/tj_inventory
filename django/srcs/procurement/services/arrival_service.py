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
                    received_qty=item_data.get('received_qty', 0),
                    mfg_date=item_data.get('mfg_date'),
                    exp_date=item_data.get('exp_date'),
                    created_by=user
                )
        # Trigger auto-allocation of pending shortages
        ArrivalService.allocate_shortages_for_arrival(arrival, user=user)
        
        return arrival

    @staticmethod
    @transaction.atomic
    def update(arrival, *, user, items_data=None, **fields):
        """
        Update an Arrival document and its items.
        """
        if arrival.status == Arrival.Status.RECEIVED:
            raise ValidationError("Cannot update an arrival that has already been received.")

        old_status = arrival.status
        # Update header fields
        for field, value in fields.items():
            setattr(arrival, field, value)
        
        arrival.updated_by = user
        arrival.full_clean()
        arrival.save()

        if items_data is not None:
            ArrivalService.sync_items(arrival, items_data, user=user)

        # Revert allocations if cancelled
        if arrival.status == Arrival.Status.CANCELLED and old_status != Arrival.Status.CANCELLED:
            ArrivalService.release_reservations_and_revert_to_shortages(arrival, user=user)
        else:
            # Re-allocate shortages for the arrival
            ArrivalService.allocate_shortages_for_arrival(arrival, user=user)

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

        # Revert allocations back to shortages
        ArrivalService.release_reservations_and_revert_to_shortages(arrival, user=user)

        # 3. Soft-delete the arrival
        arrival.delete(user=user)
        return arrival

    @staticmethod
    def sync_items(arrival, items_data, user=None):
        """
        Sync ArrivalItems based on formset data.
        """
        existing_items = {item.id: item for item in arrival.items.filter(is_deleted=False)}
        
        for item_info in items_data:
            if not item_info:
                continue

            item_id = item_info.get('id')
            is_delete = item_info.get('DELETE', False)
            
            if is_delete:
                if item_id and item_id in existing_items:
                    existing_items[item_id].delete(user=user)
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
                item.mfg_date = item_info.get('mfg_date')
                item.exp_date = item_info.get('exp_date')
                if user:
                    item.updated_by = user
                item.save()
            else:
                # Create new
                ArrivalItem.objects.create(
                    arrival=arrival,
                    item=item_info['item'],
                    po_item=item_info.get('po_item'),
                    packaging=item_info.get('packaging'),
                    expected_qty=item_info['expected_qty'],
                    received_qty=0,
                    mfg_date=item_info.get('mfg_date'),
                    exp_date=item_info.get('exp_date'),
                    created_by=user
                )

    @staticmethod
    @transaction.atomic
    def initiate_receiving(arrival, user, receive_quantities=None):
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
        for arrival_item in arrival.items.filter(is_deleted=False):
            qty = arrival_item.expected_qty
            if receive_quantities and arrival_item.id in receive_quantities:
                qty = receive_quantities[arrival_item.id]

            if arrival_item.packaging and arrival_item.packaging.quantity:
                qty = qty * arrival_item.packaging.quantity

            unit_cost = arrival_item.po_item.unit_cost if arrival_item.po_item else None
            if unit_cost is not None and arrival_item.packaging and arrival_item.packaging.quantity:
                unit_cost = unit_cost / arrival_item.packaging.quantity

            exp_date_str = arrival_item.exp_date.strftime("%Y%m%d") if arrival_item.exp_date else "PENDING"
            MovementService.add_item(
                movement,
                item=arrival_item.item,
                lot_number=f'LOT-{arrival_item.item.sku}-{exp_date_str}',
                quantity=qty,
                user=user,
                unit_cost=unit_cost,
                mfg_date=arrival_item.mfg_date,
                exp_date=arrival_item.exp_date,
                arrival_item=arrival_item,
                note=arrival_item.arrival.note
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
        
        for arrival_item in arrival.items.filter(is_deleted=False):
            total_received_pieces = InventoryMovementItem.objects.filter(
                arrival_item=arrival_item,
                movement__status='completed' # status is a string choice
            ).aggregate(total=Sum('quantity'))['total'] or 0

            if arrival_item.packaging and arrival_item.packaging.quantity:
                arrival_item.received_qty = total_received_pieces / arrival_item.packaging.quantity
            else:
                arrival_item.received_qty = total_received_pieces
            arrival_item.save()

            # --- PROMOTION OF ARRIVAL RESERVATIONS TO PHYSICAL STOCK RESERVATIONS ---
            # Find the movement item(s) for this arrival_item in the completed movement
            m_items = InventoryMovementItem.objects.filter(
                arrival_item=arrival_item,
                movement=movement
            )

            for m_item in m_items:
                from inventory.models import Stock, StockReservation
                from sales.models import SalesAllocation
                try:
                    stock = Stock.objects.get(
                        warehouse=movement.warehouse,
                        item=arrival_item.item,
                        lot_number=m_item.lot_number,
                        is_deleted=False
                    )
                except Stock.DoesNotExist:
                    continue

                from procurement.models import ArrivalReservation
                arrival_reservations = list(ArrivalReservation.objects.filter(
                    arrival_item=arrival_item,
                    is_deleted=False
                ).order_by('created_at'))

                remaining_received = m_item.quantity
                for arr_res in arrival_reservations:
                    if remaining_received <= 0:
                        break

                    promote_qty = min(arr_res.quantity, remaining_received)
                    if promote_qty <= 0:
                        continue

                    # 1. Create a physical StockReservation
                    from inventory.services import ReservationService
                    physical_lock = StockReservation.objects.create(
                        stock=stock,
                        quantity=promote_qty,
                        reference_no=arr_res.reference_no,
                        reference_type=arr_res.reference_type,
                        sales_item=arr_res.sales_item,
                        origin_arrival_item=arrival_item,
                        status=StockReservation.ReservationStatus.RESERVED,
                        created_by=user or arr_res.created_by or movement.created_by
                    )

                    # 2. Update matching SalesAllocation(s) to transition from Arrival to Stock type
                    allocations = list(SalesAllocation.objects.filter(
                        arrival_reservation=arr_res,
                        is_deleted=False
                    ))
                    
                    alloc_promote_qty = promote_qty
                    for alloc in allocations:
                        if alloc_promote_qty <= 0:
                            break
                        
                        if alloc.quantity <= alloc_promote_qty:
                            alloc_promote_qty -= alloc.quantity
                            alloc.source_type = SalesAllocation.SourceType.STOCK
                            alloc.physical_reservation = physical_lock
                            alloc.arrival_reservation = None
                            alloc.save()
                            ArrivalService._sync_sales_order_status(alloc.order_item.order)
                        else:
                            # Split allocation: create stock allocation for promoted portion
                            SalesAllocation.objects.create(
                                order_item=alloc.order_item,
                                source_type=SalesAllocation.SourceType.STOCK,
                                physical_reservation=physical_lock,
                                quantity=alloc_promote_qty,
                                is_manual=alloc.is_manual,
                                created_by=user or alloc.created_by
                            )
                            # Reduce arrival allocation quantity
                            alloc.quantity -= alloc_promote_qty
                            alloc.save()
                            ArrivalService._sync_sales_order_status(alloc.order_item.order)
                            alloc_promote_qty = 0

                    # 3. Handle partial received promotion:
                    if promote_qty < arr_res.quantity:
                        # Split off a promoted record
                        ArrivalReservation.objects.create(
                            arrival_item=arr_res.arrival_item,
                            quantity=promote_qty,
                            reference_no=arr_res.reference_no,
                            reference_type=arr_res.reference_type,
                            sales_item=arr_res.sales_item,
                            note=arr_res.note,
                            status=ArrivalReservation.ReservationStatus.PROMOTED,
                            promoted_stock_reservation=physical_lock,
                            is_deleted=True,
                            created_by=arr_res.created_by,
                            updated_by=user
                        )
                        arr_res.quantity -= promote_qty
                        arr_res.save()
                    else:
                        arr_res.status = ArrivalReservation.ReservationStatus.PROMOTED
                        arr_res.promoted_stock_reservation = physical_lock
                        arr_res.save()
                        arr_res.delete(user=user)

                    from procurement.services.reservation_service import ArrivalReservationService
                    ArrivalReservationService._sync_arrival_item_reserved_qty(arrival_item)

                    remaining_received -= promote_qty

                    # 4. Trigger stock reserved quantity sync
                    ReservationService._sync_stock_reserved_qty(stock)
                
        arrival.save()

        # If the arrival is fully received, revert any remaining unreceived reservations back to shortages
        if arrival.status == Arrival.Status.RECEIVED:
            from procurement.models import ArrivalReservation
            remaining_reservations = ArrivalReservation.objects.filter(
                arrival_item__arrival=arrival,
                is_deleted=False
            )
            for res in list(remaining_reservations):
                ArrivalService.revert_reservation_to_shortage(res, user=user)

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

    @staticmethod
    @transaction.atomic
    def allocate_shortages_for_arrival(arrival, user=None):
        """
        Scan all ArrivalItems of the arrival and match them against pending shortages
        in the system using FIFO logic (oldest shortages first).
        Only matches shortages associated with CONFIRMED or PREORDER Sales Orders.
        """
        from procurement.models import Shortage, ArrivalReservation
        from sales.models import SalesAllocation, SalesOrder
        from django.db.models import Sum

        if arrival.is_deleted or arrival.status == Arrival.Status.CANCELLED:
            return

        for arrival_item in arrival.items.filter(is_deleted=False):
            # Calculate currently reserved qty on this arrival item
            reserved = ArrivalReservation.objects.filter(
                arrival_item=arrival_item,
                is_deleted=False,
                status=ArrivalReservation.ReservationStatus.RESERVED
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            available_qty = arrival_item.expected_pieces - reserved
            if available_qty <= 0:
                continue

            # Find PO-created shortages for this item associated with confirmed or preorder Sales Orders, ordered by FIFO (oldest first)
            query_filters = {
                'item': arrival_item.item,
                'status': Shortage.Status.PO_CREATED,
                'is_deleted': False,
                'sales_allocations__order_item__order__status__in': [
                    SalesOrder.Status.CONFIRMED,
                    SalesOrder.Status.PREORDER
                ]
            }
            if arrival.purchase_order:
                query_filters['purchase_order'] = arrival.purchase_order

            po_created_shortages = Shortage.objects.filter(**query_filters).order_by('created_at').distinct()

            for shortage in po_created_shortages:
                if available_qty <= 0:
                    break

                # How much can we allocate to this shortage?
                take_qty = min(shortage.request_qty, available_qty)
                if take_qty <= 0:
                    continue

                # Find the active SalesAllocation(s) linking to this shortage
                allocations = SalesAllocation.objects.filter(
                    shortage=shortage,
                    is_deleted=False
                )

                for alloc in allocations:
                    if available_qty <= 0:
                        break

                    # Allocate to this allocation
                    alloc_take = min(alloc.quantity, available_qty)
                    if alloc_take <= 0:
                        continue

                    # Create an ArrivalReservation
                    arrival_lock = ArrivalReservation.objects.create(
                        arrival_item=arrival_item,
                        quantity=alloc_take,
                        reference_no=str(alloc.order_item.order.id),
                        reference_type=ArrivalReservation.ReferenceType.SALES_ORDER,
                        sales_item=alloc.order_item,
                        created_by=user
                    )

                    # Update arrival item reserved_qty
                    arrival_item.reserved_qty = (arrival_item.reserved_qty or 0) + alloc_take
                    arrival_item.save(update_fields=['reserved_qty'])

                    # Handle partial/full allocation update
                    if alloc_take < alloc.quantity:
                        # Partial allocation: split the allocation
                        # 1. Update remaining shortage allocation qty
                        alloc.quantity -= alloc_take
                        alloc.save(update_fields=['quantity', 'updated_at'])

                        # 2. Create new allocation for the arrival reservation
                        SalesAllocation.objects.create(
                            order_item=alloc.order_item,
                            source_type=SalesAllocation.SourceType.ARRIVAL,
                            arrival_reservation=arrival_lock,
                            quantity=alloc_take,
                            is_manual=False,
                            created_by=user
                        )
                    else:
                        # Full allocation: swap the allocation source
                        alloc.source_type = SalesAllocation.SourceType.ARRIVAL
                        alloc.arrival_reservation = arrival_lock
                        alloc.shortage = None
                        alloc.save(update_fields=['source_type', 'arrival_reservation', 'shortage', 'updated_at'])

                    # Sync the order item status/allocated_qty
                    order_item = alloc.order_item
                    total_allocated = order_item.allocations.filter(is_deleted=False).aggregate(total=Sum('quantity'))['total'] or 0
                    order_item.allocated_qty = total_allocated
                    
                    real_allocated = order_item.allocations.filter(is_deleted=False).exclude(
                        source_type=SalesAllocation.SourceType.SHORTAGE
                    ).aggregate(total=Sum('quantity'))['total'] or 0
                    
                    if order_item.requested_qty > 0:
                        if real_allocated == 0:
                            order_item.status = order_item.Status.PENDING
                        elif real_allocated < order_item.requested_qty:
                            order_item.status = order_item.Status.PARTIAL
                        else:
                            order_item.status = order_item.Status.ALLOCATED
                    order_item.save(update_fields=['allocated_qty', 'status'])

                    # Sync Sales Order status
                    ArrivalService._sync_sales_order_status(order_item.order)

                    # Update the shortage record
                    if alloc_take < shortage.request_qty:
                        shortage.request_qty -= alloc_take
                        shortage.save(update_fields=['request_qty', 'updated_at'])
                    else:
                        shortage.delete()

                    available_qty -= alloc_take

    @staticmethod
    @transaction.atomic
    def revert_reservation_to_shortage(res, user=None):
        """
        Revert a single ArrivalReservation back to a pending Shortage,
        updating the SalesAllocation accordingly.
        """
        from procurement.models import Shortage
        from sales.models import SalesAllocation
        from procurement.services.reservation_service import ArrivalReservationService
        from procurement.services.shortage_service import ShortageService
        from django.db.models import Sum
        
        # 1. Get the active SalesAllocation for this reservation
        allocations = SalesAllocation.objects.filter(
            arrival_reservation=res,
            is_deleted=False
        )

        for alloc in allocations:
            order_item = alloc.order_item

            # 2. Check if a pending shortage already exists for this order item to reuse
            existing_shortage = Shortage.objects.filter(
                reference_id=str(order_item.order.id),
                reference_type=Shortage.ReferenceType.SELL_ORDER,
                item=order_item.item,
                status=Shortage.Status.PENDING,
                is_deleted=False
            ).first()

            if existing_shortage:
                existing_shortage.request_qty += alloc.quantity
                existing_shortage.save(update_fields=['request_qty', 'updated_at'])
                shortage_record = existing_shortage
            else:
                shortage_record = ShortageService.create(
                    item=order_item.item,
                    request_qty=alloc.quantity,
                    user=user or order_item.order.created_by,
                    reference_type=Shortage.ReferenceType.SELL_ORDER,
                    reference_id=str(order_item.order.id),
                    expected_date=order_item.order.order_date,
                    note=f"Reverted shortage from cancelled/short arrival {res.arrival_item.arrival.document_no}"
                )

            # 3. Transition SalesAllocation back to SHORTAGE
            alloc.source_type = SalesAllocation.SourceType.SHORTAGE
            alloc.shortage = shortage_record
            alloc.arrival_reservation = None
            alloc.save(update_fields=['source_type', 'shortage', 'arrival_reservation', 'updated_at'])

            # 4. Sync SalesOrderItem status/allocated_qty
            total_allocated = order_item.allocations.filter(is_deleted=False).aggregate(total=Sum('quantity'))['total'] or 0
            order_item.allocated_qty = total_allocated
            
            real_allocated = order_item.allocations.filter(is_deleted=False).exclude(
                source_type=SalesAllocation.SourceType.SHORTAGE
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            if order_item.requested_qty > 0:
                if real_allocated == 0:
                    order_item.status = order_item.Status.PENDING
                elif real_allocated < order_item.requested_qty:
                    order_item.status = order_item.Status.PARTIAL
                else:
                    order_item.status = order_item.Status.ALLOCATED
            order_item.save(update_fields=['allocated_qty', 'status'])

            # Sync Sales Order status
            ArrivalService._sync_sales_order_status(order_item.order)

        # 5. Delete/Release the ArrivalReservation
        ArrivalReservationService.release(res, user=user)

    @staticmethod
    @transaction.atomic
    def release_reservations_and_revert_to_shortages(arrival, user=None):
        """
        Find all active reservations for the arrival and call revert_reservation_to_shortage on each.
        """
        from procurement.models import ArrivalReservation
        
        remaining_reservations = ArrivalReservation.objects.filter(
            arrival_item__arrival=arrival,
            is_deleted=False
        )
        for res in list(remaining_reservations):
            ArrivalService.revert_reservation_to_shortage(res, user=user)

    @staticmethod
    def _sync_sales_order_status(order):
        """
        Synchronize the SalesOrder status based on the allocations of its items:
        - If there is any active SHORTAGE allocation, and status is CONFIRMED or PREORDER,
          demote/transition to DRAFT.
        - If there are NO active SHORTAGE allocations:
          - If there is at least one active ARRIVAL allocation:
            - If status is DRAFT or CONFIRMED, transition to PREORDER.
          - If there are no active ARRIVAL allocations (only STOCK):
            - If status is DRAFT or PREORDER, transition to CONFIRMED.
        """
        from sales.models import SalesAllocation, SalesOrder

        if order.status not in [SalesOrder.Status.DRAFT, SalesOrder.Status.PREORDER, SalesOrder.Status.CONFIRMED]:
            return

        has_shortages = False
        has_arrivals = False

        for item in order.items.all():
            if item.allocations.filter(source_type=SalesAllocation.SourceType.SHORTAGE, is_deleted=False).exists():
                has_shortages = True
            if item.allocations.filter(source_type=SalesAllocation.SourceType.ARRIVAL, is_deleted=False).exists():
                has_arrivals = True

        if has_shortages:
            if order.status in [SalesOrder.Status.CONFIRMED, SalesOrder.Status.PREORDER]:
                order.status = SalesOrder.Status.DRAFT
                order.save(update_fields=['status', 'updated_at'])
        else:
            if has_arrivals:
                if order.status in [SalesOrder.Status.DRAFT, SalesOrder.Status.CONFIRMED]:
                    order.status = SalesOrder.Status.PREORDER
                    order.save(update_fields=['status', 'updated_at'])
            else:
                if order.status in [SalesOrder.Status.DRAFT, SalesOrder.Status.PREORDER]:
                    order.status = SalesOrder.Status.CONFIRMED
                    order.save(update_fields=['status', 'updated_at'])
