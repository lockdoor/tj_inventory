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

        # Update basic header info
        order.document_no = document_no
        order.partner = partner
        order.order_type = order_type
        order.note = note
        order.updated_by = user
        if order_date:
            order.order_date = order_date
        order.save()

        # Release allocations and delete previous items cleanly
        for item in list(order.items.all()):
            for allocation in list(item.allocations.all()):
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
                allocation.delete()
            item.delete()

        # Re-create item lines
        if items:
            for item_data in items:
                SalesService.add_item(order, **item_data)

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
            item.allocations.update(is_manual=False)
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
    def add_item(order: SalesOrder, *, item, requested_qty, unit_price):
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
            unit_price=unit_price
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
        
        # 1. CLEANUP & PRESERVATION
        for allocation in list(order_item.allocations.all()):
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
                        # We delete the volatile allocation record, but let refresh_allocation handle the shortage record update/delete below!
                        pass
                    else:
                        # PO already created! KEEP THIS ALLOCATION
                        is_volatile = False
                        remaining_qty -= allocation.quantity
            
            if is_volatile:
                allocation.delete()
 
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
            
            SalesAllocation.objects.create(
                order_item=order_item,
                source_type=SalesAllocation.SourceType.SHORTAGE,
                shortage=gap_record,
                quantity=remaining_qty,
                is_manual=False # System-picked
            )
        else:
            # If remaining_qty is 0, any existing pending shortage is no longer needed
            if existing_shortage:
                existing_shortage.delete()

        # 5. SYNC SUMMARY BACK TO ORDER ITEM
        total_allocated = order_item.allocations.aggregate(total=Sum('quantity'))['total'] or 0
        order_item.allocated_qty = total_allocated
        
        real_allocated = order_item.allocations.exclude(
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
