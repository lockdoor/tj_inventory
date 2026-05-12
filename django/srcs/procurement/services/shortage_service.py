from django.core.exceptions import ValidationError
from procurement.models import Shortage


class ShortageService:
    """
    Business logic for Shortage operations.
    """

    @staticmethod
    def get_active_queryset():
        return Shortage.objects.filter(is_deleted=False)

    @staticmethod
    def create(*, item, request_qty, user, reference_type='other', reference_id='', note=''):
        """
        Record a new shortage.
        """
        shortage = Shortage(
            item=item,
            request_qty=request_qty,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
            created_by=user,
            status=Shortage.Status.PENDING
        )
        shortage.full_clean()
        shortage.save()
        return shortage

    @staticmethod
    def link_to_po(shortage, po, *, user):
        """
        Link a shortage to a PO once it's been ordered.
        """
        shortage.purchase_order = po
        shortage.status = Shortage.Status.PO_CREATED
        shortage.updated_by = user
        shortage.save()
        return shortage

    @staticmethod
    def cancel(shortage, *, user, note=None):
        """
        Cancel a shortage if it's no longer needed.
        """
        shortage.status = Shortage.Status.CANCELLED
        if note:
            shortage.note = note
        shortage.updated_by = user
        shortage.save()
        return shortage

    @staticmethod
    def soft_delete(shortage, *, user):
        """Soft-delete the shortage record."""
        shortage.is_deleted = True
        shortage.updated_by = user
        shortage.save()
        return shortage
