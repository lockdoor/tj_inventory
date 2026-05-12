from django.db import transaction
from django.core.exceptions import ValidationError
from procurement.models import Arrival, ArrivalItem


class ArrivalService:
    """
    Business logic for Arrival operations.
    """

    @staticmethod
    def get_active_queryset():
        return Arrival.objects.filter(is_deleted=False)

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
                    expected_qty=item_data['expected_qty'],
                    received_qty=item_data.get('received_qty', 0)
                )
        
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
    def soft_delete(arrival, *, user):
        """Soft-delete the arrival."""
        if arrival.status == Arrival.Status.RECEIVED:
            raise ValidationError("Cannot delete an arrival that has already been received.")
        
        arrival.is_deleted = True
        arrival.updated_by = user
        arrival.save()
        return arrival
