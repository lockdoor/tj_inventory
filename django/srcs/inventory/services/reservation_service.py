from django.db import transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError
from ..models import Stock, StockReservation


class ReservationService:
    """
    Service to manage physical stock reservations (holds).
    Used by Sales, Production, and other modules to lock items on the shelf.
    """

    @staticmethod
    def _sync_stock_reserved_qty(stock):
        """
        Internal helper to keep Stock.reserved_qty in sync with actual reservation records.
        Handles optimistic locking by refreshing the version before saving.
        """
        total_reserved = StockReservation.objects.filter(
            stock=stock
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # To handle optimistic locking (AuditableMixin.version), 
        # we refresh the object to get the latest version before updating
        stock.refresh_from_db()
        stock.reserved_qty = total_reserved
        stock.save(update_fields=['reserved_qty', 'version'])

    @staticmethod
    @transaction.atomic
    def reserve(stock, quantity, reference_no, reference_type=StockReservation.ReferenceType.SALES_ORDER, sales_item=None, note=''):
        """
        Create a hard reservation against a specific stock record.
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than zero")

        # Check availability: balance - current reservations
        reserved = StockReservation.objects.filter(stock=stock).aggregate(total=Sum('quantity'))['total'] or 0
        available = stock.balance - reserved

        if quantity > available:
            raise ValidationError(
                f"Insufficient available stock for Lot {stock.lot_number}. "
                f"Requested: {quantity}, Available: {available}"
            )

        reservation = StockReservation.objects.create(
            stock=stock,
            quantity=quantity,
            reference_no=reference_no,
            reference_type=reference_type,
            sales_item=sales_item,
            note=note
        )
        
        # Explicitly sync the stock record
        ReservationService._sync_stock_reserved_qty(stock)
        
        return reservation

    @staticmethod
    @transaction.atomic
    def update_reservation(reservation, new_quantity):
        """
        Update the quantity of an existing reservation.
        """
        if new_quantity <= 0:
            return ReservationService.release(reservation)

        diff = new_quantity - reservation.quantity
        if diff > 0:
            # If increasing, check availability again
            reserved = StockReservation.objects.filter(
                stock=reservation.stock
            ).exclude(pk=reservation.pk).aggregate(total=Sum('quantity'))['total'] or 0
            
            available = reservation.stock.balance - reserved
            if new_quantity > available:
                raise ValidationError(f"Insufficient available stock to increase reservation to {new_quantity}")

        reservation.quantity = new_quantity
        reservation.save()
        
        # Explicitly sync the stock record
        ReservationService._sync_stock_reserved_qty(reservation.stock)
        
        return reservation

    @staticmethod
    @transaction.atomic
    def release(reservation):
        """
        Permanently remove a reservation (unlock the stock).
        """
        stock = reservation.stock
        reservation.delete()
        
        # Explicitly sync the stock record
        ReservationService._sync_stock_reserved_qty(stock)
        
        return True

    @staticmethod
    @transaction.atomic
    def delete_by_reference(reference_no, reference_type):
        """
        Release all reservations associated with a specific document.
        """
        # Find all affected stocks first
        affected_stocks = list(Stock.objects.filter(
            reservations__reference_no=reference_no,
            reservations__reference_type=reference_type
        ).distinct())
        
        # Delete the reservations
        StockReservation.objects.filter(
            reference_no=reference_no,
            reference_type=reference_type
        ).delete()
        
        # Sync each affected stock
        for stock in affected_stocks:
            ReservationService._sync_stock_reserved_qty(stock)
            
        return True
