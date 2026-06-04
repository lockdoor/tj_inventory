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
