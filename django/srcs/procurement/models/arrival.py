from django.db import models
from common.mixins.auditable import AuditableMixin


class Arrival(AuditableMixin):
    """
    Represents an incoming shipment from a supplier.
    """
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        RECEIVING = 'receiving', 'Receiving'
        RECEIVED = 'received', 'Received'
        CANCELLED = 'cancelled', 'Cancelled'

    document_no = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique arrival document number"
    )
    purchase_order = models.ForeignKey(
        'procurement.PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='arrivals',
        help_text="Original Purchase Order (optional)"
    )
    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        related_name='arrivals',
        help_text="Supplier shipping the goods"
    )
    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.PROTECT,
        related_name='arrivals',
        help_text="Destination warehouse"
    )
    expected_date = models.DateField(
        help_text="Expected arrival date"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        help_text="Current status of the shipment"
    )
    note = models.TextField(
        blank=True,
        default='',
        help_text="Internal notes about this shipment"
    )

    class Meta:
        ordering = ['-expected_date', '-created_at']
        verbose_name = "Arrival"
        verbose_name_plural = "Arrivals"

    def __str__(self):
        return f"{self.document_no} ({self.partner.name})"


class ArrivalItem(AuditableMixin):
    """
    Individual item line in an Arrival document.
    """
    arrival = models.ForeignKey(
        Arrival,
        on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        'catalog.Item',
        on_delete=models.PROTECT,
        related_name='arrival_items'
    )
    packaging = models.ForeignKey(
        'catalog.ItemPackaging',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='arrival_items',
        help_text="Received packaging container (optional)"
    )
    po_item = models.ForeignKey(
        'procurement.PurchaseOrderItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='arrival_items',
        help_text="Link to specific PO line for fulfillment tracking"
    )
    expected_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Quantity expected according to shipment"
    )
    received_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Actual quantity received in warehouse"
    )
    reserved_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Quantity committed to Sell Orders"
    )
    mfg_date = models.DateField(
        null=True,
        blank=True,
        help_text="Manufacturing date"
    )
    exp_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expiry date"
    )

    @property
    def available_qty(self):
        """Expected quantity remaining after reservations."""
        return max(0, self.expected_qty - self.reserved_qty)

    class Meta:
        verbose_name = "Arrival Item"
        verbose_name_plural = "Arrival Items"

    def __str__(self):
        return f"{self.arrival.document_no} - {self.item.sku} ({self.received_qty}/{self.expected_qty})"
