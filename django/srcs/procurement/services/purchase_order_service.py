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
    @transaction.atomic
    def sync_items(po, items_data):
        """
        Synchronize PO items.
        items_data: list of dicts {'item': Item, 'order_qty': qty, 'unit_cost': cost, 'is_deleted': bool}
        """
        for item_data in items_data:
            item_instance = item_data.get('instance')
            if item_data.get('is_deleted', False):
                if item_instance:
                    item_instance.delete()
                continue
            
            if item_instance:
                item_instance.item = item_data['item']
                item_instance.order_qty = item_data['order_qty']
                item_instance.unit_cost = item_data.get('unit_cost')
                item_instance.save()
            else:
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    item=item_data['item'],
                    order_qty=item_data['order_qty'],
                    unit_cost=item_data.get('unit_cost')
                )

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

    @staticmethod
    @transaction.atomic
    def submit(po, *, user):
        """Transition PO from DRAFT to SUBMITTED."""
        if po.status != PurchaseOrder.Status.DRAFT:
            raise ValidationError("Only Draft Purchase Orders can be submitted.")
        
        po.status = PurchaseOrder.Status.SUBMITTED
        po.updated_by = user
        po.save()
        return po

    @staticmethod
    @transaction.atomic
    def revert_to_draft(po, *, user):
        """Transition PO from SUBMITTED back to DRAFT."""
        if po.status != PurchaseOrder.Status.SUBMITTED:
            raise ValidationError("Only Submitted Purchase Orders can be reverted.")
        
        po.status = PurchaseOrder.Status.DRAFT
        po.updated_by = user
        po.save()
        return po
