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
                    packaging=item_data.get('packaging'),
                    order_qty=item_data['order_qty'],
                    unit_cost=item_data.get('unit_cost')
                )
        
        return po

    @staticmethod
    @transaction.atomic
    def create_from_shortages(*, document_no, partner, user, expected_date=None, note='', items=None, shortage_ids=None):
        """
        Create a new Purchase Order from selected shortages.
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
                    packaging=item_data.get('packaging'),
                    order_qty=item_data['order_qty'],
                    unit_cost=item_data.get('unit_cost')
                )

        if shortage_ids:
            from procurement.models import Shortage
            from procurement.services.shortage_service import ShortageService
            shortages = Shortage.objects.filter(id__in=shortage_ids, is_deleted=False, status=Shortage.Status.PENDING)
            
            # Backend validation check: PO expected date should not be less than any shortage expected date
            if expected_date:
                from datetime import date, datetime
                val_date = expected_date
                if isinstance(val_date, str):
                    val_date = datetime.strptime(val_date, '%Y-%m-%d').date()
                elif isinstance(val_date, datetime):
                    val_date = val_date.date()
                
                for shortage in shortages:
                    if shortage.expected_date and val_date < shortage.expected_date:
                        raise ValidationError(
                            f"Purchase Order expected date ({val_date.strftime('%Y-%m-%d')}) "
                            f"cannot be earlier than shortage expected date of "
                            f"{shortage.expected_date.strftime('%Y-%m-%d')} for {shortage.item.sku}."
                        )

            for shortage in shortages:
                ShortageService.link_to_po(shortage, po, user=user)

        return po

    @staticmethod
    @transaction.atomic
    def update(po, *, user, **fields):
        """
        Update PO header fields.
        """
        allowed_fields = ['expected_date', 'note', 'status']
        
        # Check expected_date constraints against linked shortages
        if 'expected_date' in fields and fields['expected_date']:
            val_date = fields['expected_date']
            from datetime import date, datetime
            if isinstance(val_date, str):
                val_date = datetime.strptime(val_date, '%Y-%m-%d').date()
            elif isinstance(val_date, datetime):
                val_date = val_date.date()
            
            for shortage in po.shortages.filter(is_deleted=False):
                if shortage.expected_date and val_date < shortage.expected_date:
                    raise ValidationError(
                        f"Purchase Order expected date ({val_date.strftime('%Y-%m-%d')}) "
                        f"cannot be earlier than shortage expected date of "
                        f"{shortage.expected_date.strftime('%Y-%m-%d')} for {shortage.item.sku}."
                    )
        
        # Check transition rules if status is changing
        if 'status' in fields and fields['status'] != po.status:
            PurchaseOrderService._validate_status_transition(po, fields['status'])

        for field, value in fields.items():
            if field in allowed_fields:
                setattr(po, field, value)

        po.updated_by = user
        po.full_clean()
        po.save()

        # If status was changed to CANCELLED, revert any linked shortages back to pending
        if fields.get('status') == PurchaseOrder.Status.CANCELLED:
            po.shortages.filter(is_deleted=False).update(
                status='pending',
                purchase_order=None,
                updated_by=user
            )

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
                item_instance.packaging = item_data.get('packaging')
                item_instance.order_qty = item_data['order_qty']
                item_instance.unit_cost = item_data.get('unit_cost')
                item_instance.save()
            else:
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    item=item_data['item'],
                    packaging=item_data.get('packaging'),
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
        
        # Check if active arrivals exist
        if po.arrivals.filter(is_deleted=False).exists():
            raise ValidationError("Cannot delete Purchase Order because it has scheduled or received arrivals.")
        
        with transaction.atomic():
            po.is_deleted = True
            po.updated_by = user
            po.save()

            # Revert any linked shortages back to pending
            po.shortages.filter(is_deleted=False).update(
                status='pending',
                purchase_order=None,
                updated_by=user
            )
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

        arrivals = po.arrivals.filter()
        
        if arrivals.filter(is_deleted=False).exists():
            raise ValidationError("Cannot revert to draft because this Purchase Order has scheduled or received arrivals.")

        # hard delete arrivals if exists
        arrivals.all().delete()
        
        po.status = PurchaseOrder.Status.DRAFT
        po.updated_by = user
        po.save()
        return po

    @staticmethod
    @transaction.atomic
    def close(po, *, user):
        """Transition PO to CLOSED status."""
        if po.status != PurchaseOrder.Status.SUBMITTED:
            raise ValidationError("Only Submitted Purchase Orders can be closed.")
        
        po.status = PurchaseOrder.Status.CLOSED
        po.updated_by = user
        po.save()
        return po

    @staticmethod
    def get_suggested_PO_numbers():
        from django.utils import timezone
        today_str = timezone.now().strftime('%Y%m%d')
        prefix = f"PO-{today_str}-"
        last_po = PurchaseOrder.objects.filter(document_no__startswith=prefix).order_by('-document_no').first()
        if last_po:
            try:
                last_serial = int(last_po.document_no.split('-')[-1])
                new_serial = last_serial + 1
            except ValueError:
                new_serial = 1
        else:
            new_serial = 1
        suggested_no = f"{prefix}{new_serial:04d}"
        return suggested_no