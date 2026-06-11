from django.db import models
from django.core.exceptions import ValidationError
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

    def delete(self, user=None, *args, **kwargs):
        self.refresh_version()
        # Cascade soft-delete to child items
        for item in self.items.filter(is_deleted=False):
            item.delete(user=user, *args, **kwargs)
        super().delete(user=user, *args, **kwargs)

    def restore(self):
        # Cascade restore to child items
        for item in self.items.filter(is_deleted=True):
            item.restore()
        super().restore()



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
    def expected_pieces(self):
        """Total expected quantity in base units (pieces)."""
        if self.packaging and self.packaging.quantity:
            return self.expected_qty * self.packaging.quantity
        return self.expected_qty

    @property
    def received_pieces(self):
        """Total received quantity in base units (pieces)."""
        if self.packaging and self.packaging.quantity:
            return self.received_qty * self.packaging.quantity
        return self.received_qty

    @property
    def available_qty(self):
        """Expected quantity remaining after reservations (in base pieces)."""
        return max(0, self.expected_pieces - self.reserved_qty)

    class Meta:
        verbose_name = "Arrival Item"
        verbose_name_plural = "Arrival Items"

    def clean(self):
        super().clean()
        if self.pk:
            from procurement.models.reservation import ArrivalReservation
            total_reserved = ArrivalReservation.objects.filter(
                arrival_item=self,
                is_deleted=False
            ).aggregate(total=models.Sum('quantity'))['total'] or 0

            if self.expected_pieces < total_reserved:
                req_qty_pkg = total_reserved
                if self.packaging and self.packaging.quantity:
                    req_qty_pkg = total_reserved / self.packaging.quantity
                
                pkg_name = self.packaging.name if self.packaging else "pcs"
                raise ValidationError({
                    'expected_qty': f"Cannot reduce expected quantity below currently reserved quantity of {req_qty_pkg:.2f} {pkg_name} ({total_reserved} pcs)."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, user=None, *args, **kwargs):
        from procurement.models.reservation import ArrivalReservation
        from procurement.services.arrival_service import ArrivalService
        
        # Revert active reservations back to shortages
        reservations = ArrivalReservation.objects.filter(arrival_item=self, is_deleted=False)
        for res in list(reservations):
            ArrivalService.revert_reservation_to_shortage(res, user=user)
            
        self.refresh_version()
        super().delete(user=user, *args, **kwargs)

    def __str__(self):
        return f"{self.arrival.document_no} - {self.item.sku} ({self.received_qty}/{self.expected_qty})"
