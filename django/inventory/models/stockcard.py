from django.db import models
from common.mixins import AuditableMixin

class StockCard(AuditableMixin):
    """
    The ledger entry for all inventory changes. 
    Every movement results in a StockCard record for full traceability.
    """
    class StockCardType(models.TextChoices):
        IN = 'in', 'In'
        OUT = 'out', 'Out'

    stock = models.ForeignKey(
        'inventory.Stock',
        on_delete=models.CASCADE,
        related_name='stock_cards',
        help_text="The impacted stock balance record"
    )
    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.CASCADE,
        related_name='stock_cards',
        help_text="Snapshot of the warehouse at transaction time"
    )
    item = models.ForeignKey(
        'catalog.Item',
        on_delete=models.CASCADE,
        related_name='stock_cards',
        help_text="Snapshot of the item at transaction time"
    )
    lot_number = models.CharField(
        max_length=100,
        help_text="Snapshot of the batch/lot number"
    )
    movement_item = models.ForeignKey(
        'inventory.InventoryMovementItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_cards',
        help_text="Source movement line item"
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Magnitude of change"
    )
    type = models.CharField(
        max_length=10,
        choices=StockCardType.choices,
        default=StockCardType.IN,
        help_text="Direction of change (in/out)"
    )
    note = models.TextField(
        blank=True,
        default='',
        help_text="Audit notes for this entry"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Stock Card"
        verbose_name_plural = "Stock Cards"
        indexes = [
            models.Index(fields=['lot_number']),
            models.Index(fields=['warehouse', 'item']),
        ]

    def __str__(self):
        return f"{self.created_at.strftime('%Y-%m-%d %H:%M')} | {self.lot_number} | {self.get_type_display()} {self.quantity}"
