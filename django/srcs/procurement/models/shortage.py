from django.db import models
from common.mixins.auditable import AuditableMixin


class Shortage(AuditableMixin):
    """
    Represents a shortage of items needed for demand (e.g. Sell orders or Production).
    Helps the Stock Controller decide what to purchase.
    """
    class ReferenceType(models.TextChoices):
        SELL_ORDER = 'sell_order', 'Sell Order'
        PRODUCTION = 'production', 'Production'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PO_CREATED = 'po_created', 'PO Created'
        PROMOTED = 'promoted', 'Promoted'
        CANCELLED = 'cancelled', 'Cancelled'

    item = models.ForeignKey(
        'catalog.Item',
        on_delete=models.CASCADE,
        related_name='shortages',
        help_text="The item that is in short supply"
    )
    request_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Quantity needed to fulfill the demand"
    )
    reference_type = models.CharField(
        max_length=20,
        choices=ReferenceType.choices,
        default=ReferenceType.OTHER,
        help_text="The source of the demand"
    )
    reference_id = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="ID or document number of the source (e.g. Sell order #123)"
    )
    expected_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when the items are expected to be needed"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Current status of the shortage record"
    )
    purchase_order = models.ForeignKey(
        'procurement.PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shortages',
        help_text="The PO created to address this shortage"
    )
    promoted_arrival_reservation = models.ForeignKey(
        'procurement.ArrivalReservation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='promoted_shortages',
        help_text="The arrival reservation created when this shortage was promoted"
    )
    note = models.TextField(
        blank=True,
        default='',
        help_text="Internal notes about this shortage"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Shortage"
        verbose_name_plural = "Shortages"

    def __str__(self):
        return f"Shortage: {self.item.sku} ({self.request_qty}) - {self.status}"

    @property
    def reference_display_name(self) -> str:
        """
        Returns a human-readable display name for the reference.
        If it's a sales order, tries to resolve the document number using the database ID.
        Otherwise, returns the raw reference_id.
        """
        if self.reference_type == self.ReferenceType.SELL_ORDER and self.reference_id:
            from sales.models import SalesOrder
            try:
                if not hasattr(self, '_cached_sales_order'):
                    self._cached_sales_order = SalesOrder.objects.filter(id=int(self.reference_id)).first()
                if self._cached_sales_order:
                    return self._cached_sales_order.document_no
            except (ValueError, TypeError):
                pass
        return self.reference_id


    # =========================================================================
    # SourcingAllocationSource Protocol Implementation (Duck-Typing)
    # =========================================================================
    # These properties and methods satisfy the interface defined in:
    # common/interfaces.py -> SourcingAllocationSource
    # =========================================================================

    @property
    def allocated_quantity(self):
        """
        Duck-type property satisfying SourcingAllocationSource.
        Returns the requested quantity of the shortage.
        """
        return self.request_qty

    @property
    def document_reference(self):
        """
        Duck-type property satisfying SourcingAllocationSource.
        Returns the reference document ID (e.g. sales order document_no).
        """
        return self.reference_id

    @property
    def source_item(self):
        """
        Duck-type property satisfying SourcingAllocationSource.
        Returns the catalog item associated with the shortage.
        """
        return self.item

    def release(self, user=None):
        """
        Duck-type method satisfying SourcingAllocationSource.
        If the shortage status is 'pending', soft-deletes the shortage.
        """
        if self.status == 'pending':
            self.delete(user=user)

    def delete(self, user=None, *args, **kwargs):
        self.status = self.Status.CANCELLED
        super().delete(user=user, *args, **kwargs)

    def restore(self, *args, **kwargs):
        if self.status == self.Status.CANCELLED:
            self.status = self.Status.PENDING
        super().restore(*args, **kwargs)

    def save(self, *args, **kwargs):
        modified_fields = set()
        if self.is_deleted:
            if self.status != self.Status.CANCELLED:
                self.status = self.Status.CANCELLED
                modified_fields.add('status')
            from django.utils import timezone
            if not self.deleted_at:
                self.deleted_at = timezone.now()
                modified_fields.add('deleted_at')
            if not self.deleted_by and getattr(self, 'updated_by', None):
                self.deleted_by = self.updated_by
                modified_fields.add('deleted_by')
        elif self.status == self.Status.CANCELLED:
            if not self.is_deleted:
                self.is_deleted = True
                modified_fields.add('is_deleted')
            from django.utils import timezone
            if not self.deleted_at:
                self.deleted_at = timezone.now()
                modified_fields.add('deleted_at')
            if not self.deleted_by and getattr(self, 'updated_by', None):
                self.deleted_by = self.updated_by
                modified_fields.add('deleted_by')

        if modified_fields and 'update_fields' in kwargs and kwargs['update_fields'] is not None:
            update_fields = set(kwargs['update_fields'])
            update_fields.update(modified_fields)
            kwargs['update_fields'] = update_fields

        super().save(*args, **kwargs)

