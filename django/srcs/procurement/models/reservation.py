from django.db import models


class ArrivalReservation(models.Model):
    """
    Commitment ledger for Incoming Arrivals.
    Procurement team uses this to know what is pre-sold before it arrives.
    """
    # Future Link (Required)
    class ReferenceType(models.TextChoices):
        SALES_ORDER = 'sales_order', 'Sales Order'
        PRODUCTION = 'production', 'Production'
        INTERNAL = 'internal', 'Internal Transfer'
        HOLD = 'hold', 'Quality/Maintenance Hold'

    # Future Link (Required)
    arrival_item = models.ForeignKey(
        'procurement.ArrivalItem',
        on_delete=models.CASCADE,
        related_name='reservations',
        help_text="The incoming shipment line being reserved"
    )
    
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Quantity reserved from the incoming shipment"
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
    # Using string to avoid circular dependency
    sales_item = models.ForeignKey(
        'sales.SalesOrderItem',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='arrival_reservations'
    )
    
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='arrival_reservations',
        null=True,
        blank=True,
        help_text="User who created this arrival reservation"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = "Arrival Reservation"
        verbose_name_plural = "Arrival Reservations"
        ordering = ['-created_at']

    def __str__(self):
        return f"PRE-SOLD: {self.reference_no} | {self.arrival_item} ({self.quantity})"
