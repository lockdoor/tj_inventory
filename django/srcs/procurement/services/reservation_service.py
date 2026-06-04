from django.db import transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError
from ..models import ArrivalItem, ArrivalReservation


class ArrivalReservationService:
    """
    Service to manage commitments against future stock (Arrivals).
    Used by Sales and Planning to pre-sell items before they land.
    """

    @staticmethod
    def _sync_arrival_item_reserved_qty(arrival_item):
        """
        Internal helper to keep ArrivalItem.reserved_qty in sync with reservation records.
        """
        total_reserved = ArrivalReservation.objects.filter(
            arrival_item=arrival_item,
            is_deleted=False
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        arrival_item.reserved_qty = total_reserved
        arrival_item.save(update_fields=['reserved_qty'])

    @staticmethod
    @transaction.atomic
    def reserve_future(arrival_item, quantity, reference_no, reference_type=ArrivalReservation.ReferenceType.SALES_ORDER, sales_item=None, note='', created_by=None):
        """
        Create a commitment against an incoming shipment line.
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than zero")

        # Check availability: expected_qty - current reservations
        reserved = ArrivalReservation.objects.filter(
            arrival_item=arrival_item,
            is_deleted=False
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        available = arrival_item.expected_qty - reserved

        if quantity > available:
            raise ValidationError(
                f"Insufficient expected quantity for Arrival {arrival_item.arrival.document_no}. "
                f"Requested: {quantity}, Available: {available}"
            )

        reservation = ArrivalReservation.objects.create(
            arrival_item=arrival_item,
            quantity=quantity,
            reference_no=reference_no,
            reference_type=reference_type,
            sales_item=sales_item,
            note=note,
            created_by=created_by
        )
        
        # Explicitly sync the arrival item
        ArrivalReservationService._sync_arrival_item_reserved_qty(arrival_item)
        
        return reservation

    @staticmethod
    @transaction.atomic
    def update_reservation(reservation, new_quantity):
        """
        Update the quantity of a future commitment.
        """
        if new_quantity <= 0:
            return ArrivalReservationService.release(reservation)

        diff = new_quantity - reservation.quantity
        if diff > 0:
            # If increasing, check availability against the arrival line
            reserved = ArrivalReservation.objects.filter(
                arrival_item=reservation.arrival_item,
                is_deleted=False
            ).exclude(pk=reservation.pk).aggregate(total=Sum('quantity'))['total'] or 0
            
            available = reservation.arrival_item.expected_qty - reserved
            if new_quantity > available:
                raise ValidationError(f"Insufficient expected quantity to increase reservation to {new_quantity}")

        reservation.quantity = new_quantity
        reservation.save()
        
        # Explicitly sync the arrival item
        ArrivalReservationService._sync_arrival_item_reserved_qty(reservation.arrival_item)
        
        return reservation

    @staticmethod
    @transaction.atomic
    def release(reservation, user=None):
        """
        Remove a future commitment.
        """
        arrival_item = reservation.arrival_item
        reservation.delete(user=user)
        
        # Explicitly sync the arrival item
        ArrivalReservationService._sync_arrival_item_reserved_qty(arrival_item)
        
        return True

    @staticmethod
    @transaction.atomic
    def delete_by_reference(reference_no, reference_type, user=None):
        """
        Release all future commitments associated with a specific document.
        """
        reservations = ArrivalReservation.objects.filter(
            reference_no=reference_no,
            reference_type=reference_type,
            is_deleted=False
        )
        
        # Release each reservation
        for res in list(reservations):
            ArrivalReservationService.release(res, user=user)
            
        return True
