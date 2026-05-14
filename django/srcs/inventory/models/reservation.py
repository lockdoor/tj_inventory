from django.db import models


class StockReservation(models.Model):
    """
    Physical Hold ledger for Actual Stock.
    Warehouse Admin uses this to know which physical lots are locked.
    """
    class ReferenceType(models.TextChoices):
        SALES_ORDER = 'sales_order', 'Sales Order'
        PRODUCTION = 'production', 'Production'
        INTERNAL = 'internal', 'Internal Transfer'
        HOLD = 'hold', 'Quality/Maintenance Hold'

    # Physical Link (Required)
    stock = models.ForeignKey(
        'inventory.Stock',
        on_delete=models.CASCADE,
        related_name='reservations',
        help_text="The specific physical lot being locked"
    )
    
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Physical quantity held"
    )
    
    # Context
    reference_type = models.CharField(
        max_length=20,
        choices=ReferenceType.choices,
        default=ReferenceType.SALES_ORDER
    )
    reference_no = models.CharField(
        max_length=100,
        help_text="Document number (e.g. SO-101)"
    )
    
    # Specific Link back to Sales (Optional)
    sales_item = models.ForeignKey(
        'sales.SalesOrderItem',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='physical_reservations'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = "Stock Reservation"
        verbose_name_plural = "Stock Reservations"
        ordering = ['-created_at']

    def __str__(self):
        return f"HOLD: {self.reference_no} | {self.stock.lot_number} ({self.quantity})"
