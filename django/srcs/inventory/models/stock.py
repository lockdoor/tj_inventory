from django.db import models
from common.mixins import AuditableMixin, StatusMixin

class Stock(AuditableMixin, StatusMixin):
    """
    Current stock balance for a specific lot of an item in a warehouse.
    """
    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.CASCADE,
        related_name='stocks',
        help_text="Warehouse where this stock is located"
    )
    item = models.ForeignKey(
        'catalog.Item',
        on_delete=models.CASCADE,
        related_name='stocks',
        help_text="Item in the catalog"
    )
    lot_number = models.CharField(
        max_length=100, 
        unique=True, 
        db_index=True,
        help_text="Globally unique batch/lot ID"
    )
    balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0.00,
        help_text="Current total quantity on hand for this specific lot"
    )
    reserved_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Quantity reserved for sales orders or other commitments"
    )

    mfg_date = models.DateField(
        null=True, 
        blank=True, 
        help_text="Manufacturing Date"
    )
    exp_date = models.DateField(
        null=True, 
        blank=True, 
        help_text="Expiry Date"
    )
    note = models.TextField(
        blank=True, 
        default='', 
        help_text="Internal notes about this batch"
    )

    class Meta:
        ordering = ['-exp_date', 'lot_number']
        verbose_name = "Stock"
        verbose_name_plural = "Stocks"
        indexes = [
            models.Index(fields=['lot_number']),
            models.Index(fields=['item', 'warehouse']),
        ]

    def __str__(self):
        return f"{self.lot_number} ({self.item.sku}): {self.balance}"

    def save(self, *args, **kwargs):
        """Normalize lot_number before saving."""
        if self.lot_number:
            self.lot_number = self.lot_number.strip().upper()
        super().save(*args, **kwargs)

    @property
    def available_qty(self):
        """Calculated available quantity."""
        return max(0, self.balance - self.reserved_qty)
