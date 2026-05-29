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
            stock=stock,
            is_deleted=False,
            status=StockReservation.ReservationStatus.RESERVED
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # To handle optimistic locking (AuditableMixin.version), 
        # we refresh the object to get the latest version before updating
        stock.refresh_from_db()
        stock.reserved_qty = total_reserved
        stock.save(update_fields=['reserved_qty', 'version'])

    @staticmethod
    @transaction.atomic
    def reserve(stock, quantity, reference_no, reference_type=StockReservation.ReferenceType.SALES_ORDER, sales_item=None, note='', created_by=None):
        """
        Create a hard reservation against a specific stock record.
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than zero")

        # Fallback system/superuser if created_by is None
        if not created_by:
            from django.contrib.auth.models import User
            created_by = User.objects.filter(is_superuser=True).first()
            if not created_by:
                created_by = User.objects.filter(username="system").first()
            if not created_by:
                created_by = User.objects.create_user(username="system", email="system@example.com")

        # Check availability: balance - current reservations
        reserved = StockReservation.objects.filter(
            stock=stock,
            is_deleted=False,
            status=StockReservation.ReservationStatus.RESERVED
        ).aggregate(total=Sum('quantity'))['total'] or 0
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
            note=note,
            created_by=created_by
        )

        
        # Explicitly sync the stock record
        ReservationService._sync_stock_reserved_qty(stock)
        
        return reservation

    @staticmethod
    @transaction.atomic
    def update_reservation(reservation, new_quantity, user=None):
        """
        Update the quantity of an existing reservation.
        """
        if new_quantity <= 0:
            return ReservationService.release(reservation, user=user)

        diff = new_quantity - reservation.quantity
        if diff > 0:
            # If increasing, check availability again
            reserved = StockReservation.objects.filter(
                stock=reservation.stock,
                is_deleted=False,
                status=StockReservation.ReservationStatus.RESERVED
            ).exclude(pk=reservation.pk).aggregate(total=Sum('quantity'))['total'] or 0
            
            available = reservation.stock.balance - reserved
            if new_quantity > available:
                raise ValidationError(f"Insufficient available stock to increase reservation to {new_quantity}")

        reservation.quantity = new_quantity
        if user:
            reservation.updated_by = user
        reservation.save()
        
        # Explicitly sync the stock record
        ReservationService._sync_stock_reserved_qty(reservation.stock)
        
        return reservation

    @staticmethod
    @transaction.atomic
    def release(reservation, user=None):
        """
        Permanently remove a reservation (unlock the stock).
        """
        stock = reservation.stock
        reservation.status = StockReservation.ReservationStatus.RELEASED
        reservation.delete(user=user)
        
        # Explicitly sync the stock record
        ReservationService._sync_stock_reserved_qty(stock)
        
        return True

    @staticmethod
    @transaction.atomic
    def complete(reservation, user=None):
        """
        Mark a reservation as completed (stock successfully shipped/moved).
        """
        stock = reservation.stock
        reservation.status = StockReservation.ReservationStatus.COMPLETED
        if user:
            reservation.updated_by = user
        reservation.save()
        
        # Explicitly sync the stock record
        ReservationService._sync_stock_reserved_qty(stock)
        
        return True

    @staticmethod
    @transaction.atomic
    def delete_by_reference(reference_no, reference_type, user=None):
        """
        Release all reservations associated with a specific document.
        """
        reservations = StockReservation.objects.filter(
            reference_no=reference_no,
            reference_type=reference_type,
            is_deleted=False
        )
        
        for res in list(reservations):
            ReservationService.release(res, user=user)
            
        return True
