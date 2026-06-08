from django.db import transaction
from django.db.models import Sum, F
from django.core.exceptions import ValidationError
from inventory.models import Stock, StockReservation
from procurement.models import ArrivalItem, ArrivalReservation
from ..models import SalesOrder, SalesOrderItem, SalesAllocation


class SalesService:
    """
    Business logic for Sales Orders and smart reservations.
    """

    @staticmethod
    def get_active_queryset():
        return SalesOrder.objects.filter(is_deleted=False).select_related('partner')

    @staticmethod
    @transaction.atomic
    def create_order(*, document_no, partner, user, order_date=None, order_type=SalesOrder.OrderType.NORMAL, items=None, note=''):
        """
        Create a new Sales Order and optionally its items.
        """
        create_params = {
            'document_no': document_no,
            'partner': partner,
            'order_type': order_type,
            'note': note,
            'created_by': user
        }
        if order_date:
            create_params['order_date'] = order_date

        order: SalesOrder = SalesOrder.objects.create(**create_params)
        
        if items:
            for item_data in items:
                SalesService.add_item(order, **item_data)
        
        return order

    @staticmethod
    @transaction.atomic
    def update_order(order: SalesOrder, *, document_no, partner, user, order_date=None, order_type=SalesOrder.OrderType.NORMAL, items=None, note=''):
        """
        Update an existing draft Sales Order and its item lines.
        """
        if order.status != SalesOrder.Status.DRAFT:
            raise ValidationError("Only draft sales orders can be edited.")

        # Keep track of which catalog items were manually allocated
        manual_allocate_map = {item.item_id: item.is_manual_allocate for item in order.items.all()}

        old_document_no = order.document_no
        document_no_changed = (old_document_no != document_no)

        # Update basic header info
        order.document_no = document_no
        order.partner = partner
        order.order_type = order_type
        order.note = note
        order.updated_by = user
        if order_date:
            order.order_date = order_date
        order.save()

        # If document number changed, update string references in related models
        if document_no_changed:
            from inventory.models import StockReservation
            from procurement.models import ArrivalReservation, Shortage
            StockReservation.objects.filter(
                reference_no=old_document_no,
                reference_type=StockReservation.ReferenceType.SALES_ORDER
            ).update(reference_no=document_no)
            
            ArrivalReservation.objects.filter(
                reference_no=old_document_no,
                reference_type=ArrivalReservation.ReferenceType.SALES_ORDER
            ).update(reference_no=document_no)
            
            Shortage.objects.filter(
                reference_id=old_document_no,
                reference_type=Shortage.ReferenceType.SELL_ORDER
            ).update(reference_id=document_no)

        # Reconcile item lines in-place
        existing_items = {item.item_id: item for item in order.items.all()}
        new_item_ids = set()

        if items:
            for item_data in items:
                item_obj = item_data['item']
                new_item_ids.add(item_obj.pk)
                
                requested_qty = item_data['requested_qty']
                unit_price = item_data['unit_price']
                
                if item_obj.pk in existing_items:
                    # Update existing line in-place
                    order_item = existing_items[item_obj.pk]
                    
                    # Release active stock/arrival allocations before refreshing (as edit starts fresh)
                    for allocation in list(order_item.allocations.filter(is_deleted=False)):
                        if allocation.source_type == SalesAllocation.SourceType.STOCK:
                            if allocation.physical_reservation:
                                from inventory.services import ReservationService
                                ReservationService.release(allocation.physical_reservation)
                            allocation.delete(user=user)
                        elif allocation.source_type == SalesAllocation.SourceType.ARRIVAL:
                            if allocation.arrival_reservation:
                                from procurement.services import ArrivalReservationService
                                ArrivalReservationService.release(allocation.arrival_reservation)
                            allocation.delete(user=user)
                            
                    order_item.requested_qty = requested_qty
                    order_item.unit_price = unit_price
                    order_item.save(update_fields=['requested_qty', 'unit_price'])
                    
                    # Refresh allocations to adjust the remaining shortage or auto-allocation in-place
                    SalesService.refresh_allocation(order_item)
                else:
                    # Create new line
                    is_manual = manual_allocate_map.get(item_obj.pk, False)
                    SalesService.add_item(
                        order,
                        item=item_obj,
                        requested_qty=requested_qty,
                        unit_price=unit_price,
                        is_manual_allocate=is_manual
                    )

        # Cleanly release allocations and delete lines that are no longer in the updated order
        for item_id, order_item in existing_items.items():
            if item_id not in new_item_ids:
                for allocation in list(order_item.allocations.filter(is_deleted=False)):
                    if allocation.source_type == SalesAllocation.SourceType.STOCK:
                        if allocation.physical_reservation:
                            from inventory.services import ReservationService
                            ReservationService.release(allocation.physical_reservation)
                    elif allocation.source_type == SalesAllocation.SourceType.ARRIVAL:
                        if allocation.arrival_reservation:
                            from procurement.services import ArrivalReservationService
                            ArrivalReservationService.release(allocation.arrival_reservation)
                    elif allocation.source_type == SalesAllocation.SourceType.SHORTAGE:
                        if allocation.shortage:
                            if allocation.shortage.status == 'pending':
                                allocation.shortage.delete()
                    allocation.delete(user=user)
                order_item.delete()

        return order

    @staticmethod
    @transaction.atomic
    def cancel_order(order, user):
        """
        Fully cancel an order and release all associated holds.
        """
        for item in order.items.all():
            item.requested_qty = 0
            # Note: We must clear manual flags during cancellation to release everything
            item.allocations.filter(is_deleted=False).update(is_manual=False)
            item.is_manual_allocate = False
            item.status = SalesOrderItem.Status.CANCELLED
            item.save()
            SalesService.refresh_allocation(item)
        
        order.status = SalesOrder.Status.CANCELLED
        order.updated_by = user
        order.save()
        return order

    @staticmethod
    @transaction.atomic
    def add_item(order: SalesOrder, *, item, requested_qty, unit_price, is_manual_allocate=False):
        """
        Add an item to the order and trigger initial allocation.
        """
        from decimal import Decimal
        requested_qty = Decimal(str(requested_qty))
        unit_price = Decimal(str(unit_price))

        order_item: SalesOrderItem = SalesOrderItem.objects.create(
            order=order,
            item=item,
            requested_qty=requested_qty,
            unit_price=unit_price,
            is_manual_allocate=is_manual_allocate
        )
        
        # Trigger initial allocation
        SalesService.refresh_allocation(order_item)
        
        return order_item

    @staticmethod
    @transaction.atomic
    def manual_allocate_stock(order_item: SalesOrderItem, stock: Stock, quantity: float):
        """
        Allows a user to manually pick a specific lot (Shopping Cart style).
        """
        from inventory.services import ReservationService
        physical_lock = ReservationService.reserve(
            stock=stock,
            quantity=quantity,
            reference_no=order_item.order.document_no,
            reference_type=StockReservation.ReferenceType.SALES_ORDER,
            sales_item=order_item
        )
        
        SalesAllocation.objects.create(
            order_item=order_item,
            source_type=SalesAllocation.SourceType.STOCK,
            physical_reservation=physical_lock,
            quantity=quantity,
            is_manual=True # PROTECT THIS FROM AUTO-REFRESH
        )
        
        order_item.is_manual_allocate = True
        order_item.save(update_fields=['is_manual_allocate'])
        
        # Refresh to fill any remaining gaps automatically
        SalesService.refresh_allocation(order_item)

    @staticmethod
    @transaction.atomic
    def manual_allocate_arrival(order_item: SalesOrderItem, arrival_item: ArrivalItem, quantity: float):
        """
        Allows a user to manually pick a specific incoming shipment.
        """
        from procurement.services import ArrivalReservationService
        from procurement.models import ArrivalReservation
        arrival_lock = ArrivalReservationService.reserve_future(
            arrival_item=arrival_item,
            quantity=quantity,
            reference_no=order_item.order.document_no,
            reference_type=ArrivalReservation.ReferenceType.SALES_ORDER,
            sales_item=order_item
        )
        
        SalesAllocation.objects.create(
            order_item=order_item,
            source_type=SalesAllocation.SourceType.ARRIVAL,
            arrival_reservation=arrival_lock,
            quantity=quantity,
            is_manual=True # PROTECT THIS FROM AUTO-REFRESH
        )
        
        order_item.is_manual_allocate = True
        order_item.save(update_fields=['is_manual_allocate'])
        
        # Refresh to fill any remaining gaps automatically
        SalesService.refresh_allocation(order_item)

    @staticmethod
    @transaction.atomic
    def refresh_allocation(order_item: SalesOrderItem):
        """
        The 'Smart Allocation' Engine (Gap Filler).
        1. Respects Manual selections.
        2. Respects In-Flight shortages.
        3. Fills the gap with Stock (FEFO) -> Arrivals.
        """
        if order_item.order.status != SalesOrder.Status.DRAFT:
            raise ValidationError(
                f"Cannot refresh allocations for order {order_item.order.document_no} because it is not in Draft status."
            )

        remaining_qty = order_item.requested_qty
        
        # Look up any existing pending shortage record for this order item to reuse/update instead of deleting and recreating.
        from procurement.models import Shortage
        existing_shortage = Shortage.objects.filter(
            reference_id=order_item.order.document_no,
            reference_type=Shortage.ReferenceType.SELL_ORDER,
            item=order_item.item,
            status=Shortage.Status.PENDING,
            is_deleted=False
        ).first()
        
        # Fetch soft-deleted allocations to see if they can be reused/restored
        existing_deleted_stock_allocs = {}
        existing_deleted_arrival_allocs = {}
        existing_deleted_shortage_allocs = []
        for alloc in list(order_item.allocations.filter(is_deleted=True)):
            if alloc.source_type == SalesAllocation.SourceType.STOCK:
                try:
                    if alloc.physical_reservation:
                        existing_deleted_stock_allocs[alloc.physical_reservation.stock_id] = alloc
                except Exception:
                    pass
            elif alloc.source_type == SalesAllocation.SourceType.ARRIVAL:
                try:
                    if alloc.arrival_reservation:
                        existing_deleted_arrival_allocs[alloc.arrival_reservation.arrival_item_id] = alloc
                except Exception:
                    pass
            elif alloc.source_type == SalesAllocation.SourceType.SHORTAGE:
                try:
                    if alloc.shortage:
                        existing_deleted_shortage_allocs.append(alloc)
                except Exception:
                    pass

        # 1. CLEANUP & PRESERVATION
        existing_shortage_alloc = None
        for allocation in list(order_item.allocations.filter(is_deleted=False)):
            allocation: SalesAllocation
            
            # RULE: If the user manually picked it, we KEEP it and subtract from goal.
            if allocation.is_manual:
                remaining_qty -= allocation.quantity
                continue
            
            is_volatile = True
            if allocation.source_type == SalesAllocation.SourceType.STOCK:
                if allocation.physical_reservation:
                    from inventory.services import ReservationService
                    ReservationService.release(allocation.physical_reservation)
            
            elif allocation.source_type == SalesAllocation.SourceType.ARRIVAL:
                if allocation.arrival_reservation:
                    from procurement.services import ArrivalReservationService
                    ArrivalReservationService.release(allocation.arrival_reservation)
            
            elif allocation.source_type == SalesAllocation.SourceType.SHORTAGE:
                if allocation.shortage:
                    if allocation.shortage.status == 'pending':
                        existing_shortage_alloc = allocation
                        is_volatile = False
                    else:
                        # PO already created! KEEP THIS ALLOCATION
                        is_volatile = False
                        remaining_qty -= allocation.quantity
            
            if is_volatile:
                allocation.delete(user=order_item.order.updated_by or order_item.order.created_by)
 
        # 2. AUTO-SOURCING: ACTUAL STOCK (FEFO)
        if remaining_qty > 0 and not order_item.is_manual_allocate:
            available_stocks = Stock.objects.filter(
                item=order_item.item,
                balance__gt=F('reserved_qty')
            ).order_by('exp_date', 'created_at')
            
            for stock in available_stocks:
                if remaining_qty <= 0:
                    break
                    
                free_qty = stock.available_qty
                if free_qty > 0:
                    take = min(remaining_qty, free_qty)
                    
                    from inventory.services import ReservationService
                    
                    existing_deleted_alloc = existing_deleted_stock_allocs.get(stock.pk)
                    if existing_deleted_alloc:
                        physical_lock = existing_deleted_alloc.physical_reservation
                        if physical_lock:
                            physical_lock.restore()
                            physical_lock.status = StockReservation.ReservationStatus.RESERVED
                            physical_lock.save(update_fields=['status'])
                            ReservationService.update_reservation(
                                physical_lock,
                                take,
                                user=order_item.order.updated_by or order_item.order.created_by
                            )
                        existing_deleted_alloc.restore()
                        existing_deleted_alloc.quantity = take
                        existing_deleted_alloc.is_manual = False
                        existing_deleted_alloc.save(update_fields=['quantity', 'is_manual'])
                    else:
                        physical_lock = ReservationService.reserve(
                            stock=stock,
                            quantity=take,
                            reference_no=order_item.order.document_no,
                            reference_type=StockReservation.ReferenceType.SALES_ORDER,
                            sales_item=order_item
                        )
                        SalesAllocation.objects.create(
                            order_item=order_item,
                            source_type=SalesAllocation.SourceType.STOCK,
                            physical_reservation=physical_lock,
                            quantity=take,
                            is_manual=False # System-picked
                        )
                    remaining_qty -= take

        # 3. AUTO-SOURCING: ARRIVALS
        if remaining_qty > 0 and not order_item.is_manual_allocate:
            pending_arrivals = ArrivalItem.objects.filter(
                item=order_item.item,
                arrival__status__in=['scheduled', 'receiving'],
                arrival__is_deleted=False,  # Exclude deleted arrivals
                arrival__expected_date__lte=order_item.order.order_date, # MUST ARRIVE BEFORE SO DATE
                expected_qty__gt=F('reserved_qty')
            ).order_by('arrival__expected_date')
            
            for arr_item in pending_arrivals:
                if remaining_qty <= 0:
                    break
                    
                free_qty = arr_item.available_qty
                if free_qty > 0:
                    take = min(remaining_qty, free_qty)
                    
                    from procurement.services import ArrivalReservationService
                    from procurement.models import ArrivalReservation
                    
                    existing_deleted_alloc = existing_deleted_arrival_allocs.get(arr_item.pk)
                    if existing_deleted_alloc:
                        arrival_lock = existing_deleted_alloc.arrival_reservation
                        if arrival_lock:
                            arrival_lock.restore()
                            ArrivalReservationService.update_reservation(arrival_lock, take)
                        existing_deleted_alloc.restore()
                        existing_deleted_alloc.quantity = take
                        existing_deleted_alloc.is_manual = False
                        existing_deleted_alloc.save(update_fields=['quantity', 'is_manual'])
                    else:
                        arrival_lock = ArrivalReservationService.reserve_future(
                            arrival_item=arr_item,
                            quantity=take,
                            reference_no=order_item.order.document_no,
                            reference_type=ArrivalReservation.ReferenceType.SALES_ORDER,
                            sales_item=order_item
                        )
                        SalesAllocation.objects.create(
                            order_item=order_item,
                            source_type=SalesAllocation.SourceType.ARRIVAL,
                            arrival_reservation=arrival_lock,
                            quantity=take,
                            is_manual=False # System-picked
                        )
                    remaining_qty -= take

        # 4. MARK/UPDATE SHORTAGE
        if remaining_qty > 0:
            if existing_shortage:
                # Reuse and update existing pending shortage record to keep IDs stable
                existing_shortage.request_qty = remaining_qty
                existing_shortage.save(update_fields=['request_qty', 'updated_at'])
                gap_record = existing_shortage
            else:
                from procurement.services import ShortageService
                gap_record = ShortageService.create(
                    item=order_item.item,
                    request_qty=remaining_qty,
                    user=order_item.order.created_by,
                    reference_type=Shortage.ReferenceType.SELL_ORDER,
                    reference_id=order_item.order.document_no,
                    expected_date=order_item.order.order_date,
                    note=f"Automatic shortage for {order_item.order.document_no}"
                )
            
            if existing_shortage_alloc:
                existing_shortage_alloc.quantity = remaining_qty
                existing_shortage_alloc.save(update_fields=['quantity', 'updated_at'])
            else:
                restored_alloc = None
                for del_alloc in existing_deleted_shortage_allocs:
                    if del_alloc.shortage_id == gap_record.id:
                        del_alloc.restore()
                        del_alloc.quantity = remaining_qty
                        del_alloc.is_manual = False
                        del_alloc.save(update_fields=['quantity', 'is_manual'])
                        restored_alloc = del_alloc
                        break
                
                if not restored_alloc:
                    SalesAllocation.objects.create(
                        order_item=order_item,
                        source_type=SalesAllocation.SourceType.SHORTAGE,
                        shortage=gap_record,
                        quantity=remaining_qty,
                        is_manual=False # System-picked
                    )
        else:
            # If remaining_qty is 0, any existing pending shortage is no longer needed
            if existing_shortage_alloc:
                existing_shortage_alloc.delete(user=order_item.order.updated_by or order_item.order.created_by)
            if existing_shortage:
                existing_shortage.delete()

        # 5. SYNC SUMMARY BACK TO ORDER ITEM
        total_allocated = order_item.allocations.filter(is_deleted=False).aggregate(total=Sum('quantity'))['total'] or 0
        order_item.allocated_qty = total_allocated
        
        real_allocated = order_item.allocations.filter(is_deleted=False).exclude(
            source_type=SalesAllocation.SourceType.SHORTAGE
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        if order_item.requested_qty > 0:
            if real_allocated == 0:
                order_item.status = SalesOrderItem.Status.PENDING
            elif real_allocated < order_item.requested_qty:
                order_item.status = SalesOrderItem.Status.PARTIAL
            else:
                order_item.status = SalesOrderItem.Status.ALLOCATED
            
        order_item.save(update_fields=['allocated_qty', 'status'])

    @staticmethod
    def sync_from_inventory_receipt(arrival):
        """
        Convert Arrival allocations to Stock allocations.
        """
        pass

    @staticmethod
    @transaction.atomic
    def save_manual_allocations(order_item: SalesOrderItem, user, stock_qtys: dict, arrival_qtys: dict):
        """
        Updates manual allocations/reservations for a single Sales Order Item line,
        releasing, updating or creating new allocations based on the provided inputs.
        """
        if order_item.order.status != SalesOrder.Status.DRAFT:
            raise ValidationError("Cannot manually allocate items for orders that are not in Draft status.")

        from decimal import Decimal
        from inventory.services import ReservationService
        from procurement.services import ArrivalReservationService

        # 1. Map existing manual allocations to dictionaries (both active and soft-deleted)
        existing_stock_allocs = {}
        existing_arrival_allocs = {}

        for alloc in list(order_item.allocations.all()):
            if alloc.source_type == SalesAllocation.SourceType.STOCK and alloc.physical_reservation:
                stock_id = alloc.physical_reservation.stock_id
                if stock_id not in existing_stock_allocs or not alloc.is_deleted:
                    existing_stock_allocs[stock_id] = alloc
            elif alloc.source_type == SalesAllocation.SourceType.ARRIVAL and alloc.arrival_reservation:
                arrival_item_id = alloc.arrival_reservation.arrival_item_id
                if arrival_item_id not in existing_arrival_allocs or not alloc.is_deleted:
                    existing_arrival_allocs[arrival_item_id] = alloc

        # 2. Process Stock Lot Reservations
        all_stock_ids = set(existing_stock_allocs.keys()) | set(stock_qtys.keys())
        for stock_id in all_stock_ids:
            existing_alloc = existing_stock_allocs.get(stock_id)
            submitted_qty = stock_qtys.get(stock_id, Decimal('0.00'))

            if existing_alloc:
                if submitted_qty > 0:
                    if existing_alloc.is_deleted:
                        # Restore reservation
                        reservation = existing_alloc.physical_reservation
                        if reservation:
                            reservation.restore()
                            reservation.status = StockReservation.ReservationStatus.RESERVED
                            reservation.save(update_fields=['status'])
                        # Restore allocation
                        existing_alloc.restore()

                    # Update quantity in-place
                    ReservationService.update_reservation(
                        existing_alloc.physical_reservation,
                        submitted_qty,
                        user=user
                    )
                    existing_alloc.quantity = submitted_qty
                    existing_alloc.is_manual = True
                    existing_alloc.save(update_fields=['quantity', 'is_manual'])
                else:
                    # submitted_qty is 0
                    if not existing_alloc.is_deleted:
                        if existing_alloc.physical_reservation:
                            ReservationService.release(existing_alloc.physical_reservation, user=user)
                        existing_alloc.delete(user=user)
            elif submitted_qty > 0:
                # Create new reservation + allocation
                stock = Stock.objects.filter(pk=stock_id, is_deleted=False).first()
                if not stock:
                    raise ValidationError(f"Stock lot {stock_id} does not exist or has been deleted.")
                physical_lock = ReservationService.reserve(
                    stock=stock,
                    quantity=float(submitted_qty),
                    reference_no=order_item.order.document_no,
                    reference_type=StockReservation.ReferenceType.SALES_ORDER,
                    sales_item=order_item,
                    created_by=user
                )
                SalesAllocation.objects.create(
                    order_item=order_item,
                    source_type=SalesAllocation.SourceType.STOCK,
                    physical_reservation=physical_lock,
                    quantity=submitted_qty,
                    is_manual=True
                )

        # 3. Process Arrival (Future) Reservations
        all_arrival_item_ids = set(existing_arrival_allocs.keys()) | set(arrival_qtys.keys())
        for arrival_item_id in all_arrival_item_ids:
            existing_alloc = existing_arrival_allocs.get(arrival_item_id)
            submitted_qty = arrival_qtys.get(arrival_item_id, Decimal('0.00'))

            if existing_alloc:
                if submitted_qty > 0:
                    if existing_alloc.is_deleted:
                        # Restore reservation
                        reservation = existing_alloc.arrival_reservation
                        if reservation:
                            reservation.restore()
                        # Restore allocation
                        existing_alloc.restore()

                    # Update quantity in-place
                    ArrivalReservationService.update_reservation(
                        existing_alloc.arrival_reservation,
                        submitted_qty
                    )
                    existing_alloc.quantity = submitted_qty
                    existing_alloc.is_manual = True
                    existing_alloc.save(update_fields=['quantity', 'is_manual'])
                else:
                    # submitted_qty is 0
                    if not existing_alloc.is_deleted:
                        if existing_alloc.arrival_reservation:
                            ArrivalReservationService.release(existing_alloc.arrival_reservation, user=user)
                        existing_alloc.delete(user=user)
            elif submitted_qty > 0:
                # Create new reservation + allocation
                arr_item = ArrivalItem.objects.filter(pk=arrival_item_id, arrival__is_deleted=False).first()
                if not arr_item:
                    raise ValidationError(f"Arrival item {arrival_item_id} does not exist or its arrival has been deleted.")
                if arr_item.arrival.expected_date > order_item.order.order_date:
                    raise ValidationError(
                        f"Arrival {arr_item.arrival.document_no} is expected on {arr_item.arrival.expected_date}, "
                        f"which is after the Sales Order expected fulfillment date ({order_item.order.order_date})."
                    )
                arrival_lock = ArrivalReservationService.reserve_future(
                    arrival_item=arr_item,
                    quantity=float(submitted_qty),
                    reference_no=order_item.order.document_no,
                    reference_type=ArrivalReservation.ReferenceType.SALES_ORDER,
                    sales_item=order_item,
                    created_by=user
                )
                SalesAllocation.objects.create(
                    order_item=order_item,
                    source_type=SalesAllocation.SourceType.ARRIVAL,
                    arrival_reservation=arrival_lock,
                    quantity=submitted_qty,
                    is_manual=True
                )

        order_item.is_manual_allocate = True
        order_item.save(update_fields=['is_manual_allocate'])

        # 4. Trigger smart allocation engine to calculate remaining shortages
        SalesService.refresh_allocation(order_item)

    @staticmethod
    @transaction.atomic
    def reset_allocations(order_item: SalesOrderItem, user):
        """
        Resets all manual allocations for a single Sales Order Item line back to automatic.
        """
        if order_item.order.status != SalesOrder.Status.DRAFT:
            raise ValidationError("Cannot modify allocations for orders that are not in Draft status.")

        from inventory.services import ReservationService
        from procurement.services import ArrivalReservationService

        # Release all holds
        for allocation in list(order_item.allocations.filter(is_deleted=False)):
            if allocation.source_type == SalesAllocation.SourceType.STOCK:
                if allocation.physical_reservation:
                    ReservationService.release(allocation.physical_reservation)
            elif allocation.source_type == SalesAllocation.SourceType.ARRIVAL:
                if allocation.arrival_reservation:
                    ArrivalReservationService.release(allocation.arrival_reservation)
            elif allocation.source_type == SalesAllocation.SourceType.SHORTAGE:
                if allocation.shortage:
                    if allocation.shortage.status == 'pending':
                        # Let refresh_allocation handle the shortage record update/delete
                        pass
            allocation.delete(user=user)

        order_item.is_manual_allocate = False
        order_item.save(update_fields=['is_manual_allocate'])

        # Re-run automatic waterfall matching
        SalesService.refresh_allocation(order_item)

    @staticmethod
    def get_catalog_items_data():
        """
        Fetch active catalog items with their stock lots and active reservations,
        formatted for the interactive sales order UI.
        """
        from catalog.models import Item

        # Fetch active catalog items with their stock lots and reservations preloaded
        items = Item.objects.filter(is_deleted=False, status='active').prefetch_related(
            'stocks__reservations',
            'images',
            'packagings'
        )

        items_data = []
        for item in items:
            total_balance = 0
            total_reserved = 0
            lots_data = []
            packagings_data = []

            for pkg in item.packagings.filter(is_deleted=False, status='active'):
                packagings_data.append({
                    'id': pkg.id,
                    'name': pkg.name,
                    'quantity': int(pkg.quantity),
                })

            for stock in item.stocks.filter(is_deleted=False, status='active').exclude(balance=0):
                total_balance += stock.balance
                total_reserved += stock.reserved_qty
                
                res_list = []
                # Only include active, non-soft-deleted reservations
                for res in stock.reservations.filter(is_deleted=False):
                    res_list.append({
                        'reference_no': res.reference_no,
                        'reference_type': res.get_reference_type_display(),
                        'quantity': float(res.quantity),
                        'created_by': res.created_by.username if res.created_by else 'System',
                        'note': res.note
                    })

                lots_data.append({
                    'lot_number': stock.lot_number,
                    'balance': float(stock.balance),
                    'reserved_qty': float(stock.reserved_qty),
                    'available_qty': float(stock.available_qty),
                    'exp_date': stock.exp_date.strftime('%Y-%m-%d') if stock.exp_date else 'N/A',
                    'reservations': res_list
                })

            items_data.append({
                'id': item.id,
                'sku': item.sku,
                'name': item.name,
                'unit': item.unit,
                'main_image_url': item.main_image.image.url if item.main_image else None,
                'total_balance': float(total_balance),
                'total_reserved': float(total_reserved),
                'total_available': float(max(0, total_balance - total_reserved)),
                'lots': lots_data,
                'packagings': packagings_data
            })
        return items_data

