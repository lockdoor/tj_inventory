from django.db import transaction
from django.core.exceptions import ValidationError
from procurement.models import PurchaseOrder, PurchaseOrderItem


class PurchaseOrderService:
    """
    Business logic for Purchase Order operations.
    """

    @staticmethod
    def get_active_queryset():
        """Excluded soft-deleted records."""
        return PurchaseOrder.objects.filter(is_deleted=False)

    @staticmethod
    @transaction.atomic
    def create(*, document_no, partner, user, expected_date=None, note='', items=None):
        """
        Create a new Purchase Order with optional items.
        
        Args:
            document_no: Unique PO number.
            partner: Partner instance (supplier).
            user: User instance creating the PO.
            items: List of dicts like {'item': Item, 'order_qty': 10, 'unit_cost': 5.0}
        """
        po = PurchaseOrder(
            document_no=document_no,
            partner=partner,
            expected_date=expected_date,
            note=note,
            created_by=user,
            status=PurchaseOrder.Status.DRAFT
        )
        po.full_clean()
        po.save()

        if items:
            for item_data in items:
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    item=item_data['item'],
                    order_qty=item_data['order_qty'],
                    unit_cost=item_data.get('unit_cost')
                )
        
        return po

    @staticmethod
    @transaction.atomic
    def update(po, *, user, **fields):
        """
        Update PO header fields.
        """
        allowed_fields = ['expected_date', 'note', 'status']
        
        # Check transition rules if status is changing
        if 'status' in fields and fields['status'] != po.status:
            PurchaseOrderService._validate_status_transition(po, fields['status'])

        for field, value in fields.items():
            if field in allowed_fields:
                setattr(po, field, value)

        po.updated_by = user
        po.full_clean()
        po.save()
        return po

    @staticmethod
    def _validate_status_transition(po, new_status):
        """
        Logic for valid status movements.
        """
        if po.status == PurchaseOrder.Status.CLOSED:
            raise ValidationError("Cannot change status of a closed Purchase Order.")
        
        if po.status == PurchaseOrder.Status.CANCELLED:
            raise ValidationError("Cannot change status of a cancelled Purchase Order.")

    @staticmethod
    def soft_delete(po, *, user):
        """Soft-delete the PO."""
        if po.status not in [PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.CANCELLED]:
            raise ValidationError("Only Draft or Cancelled POs can be deleted.")
        
        po.is_deleted = True
        po.updated_by = user
        po.save()
        return po
