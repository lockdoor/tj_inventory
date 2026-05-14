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
