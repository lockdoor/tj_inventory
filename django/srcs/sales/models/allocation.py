from django.db import models


class SalesAllocation(models.Model):
    """
    Fulfillment Strategy for a Sales Order Item.
    Links the customer demand to a specific source (Actual, Future, or Shortage).
    """
    class SourceType(models.TextChoices):
        STOCK = 'stock', 'Actual Stock (Physical)'
        ARRIVAL = 'arrival', 'Incoming Arrival (Future)'
        SHORTAGE = 'shortage', 'Shortage (To be purchased)'

    order_item = models.ForeignKey(
        'sales.SalesOrderItem',
        on_delete=models.CASCADE,
        related_name='allocations'
    )
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.SHORTAGE
    )
    
    # If source_type is STOCK, we link to the physical hold in inventory
    physical_reservation = models.OneToOneField(
        'inventory.StockReservation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_allocation',
        help_text="Link to the physical hold in the warehouse"
    )
    
    # If source_type is ARRIVAL, we link to the procurement reservation
    arrival_reservation = models.OneToOneField(
        'procurement.ArrivalReservation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_allocation',
        help_text="Link to the future hold in procurement"
    )
    
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Amount allocated from this source"
    )
    
    is_manual = models.BooleanField(
        default=False,
        help_text="If True, the system will not auto-recalculate this allocation"
    )
    
    # If source_type is SHORTAGE, we link to the gap ledger in procurement
    shortage = models.OneToOneField(
        'procurement.Shortage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_allocation',
        help_text="Link to the shortage record in procurement"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sales Allocation"
        verbose_name_plural = "Sales Allocations"

    def __str__(self):
        return f"{self.order_item} <- {self.get_source_type_display()} ({self.quantity})"
