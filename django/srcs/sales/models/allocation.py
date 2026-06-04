from django.db import models
from common.mixins import AuditableMixin
from common.interfaces import SourcingAllocationSource


class SalesAllocation(AuditableMixin):
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
    physical_reservation = models.ForeignKey(
        'inventory.StockReservation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_allocations',
        help_text="Link to the physical hold in the warehouse"
    )
    
    # If source_type is ARRIVAL, we link to the procurement reservation
    arrival_reservation = models.ForeignKey(
        'procurement.ArrivalReservation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_allocations',
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
    shortage = models.ForeignKey(
        'procurement.Shortage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_allocations',
        help_text="Link to the shortage record in procurement"
    )
    
    class Meta:
        verbose_name = "Sales Allocation"
        verbose_name_plural = "Sales Allocations"

    def save(self, *args, **kwargs):
        if not self.pk and (not hasattr(self, 'created_by') or self.created_by is None):
            from django.contrib.auth.models import User
            created_by = User.objects.filter(is_superuser=True).first()
            if not created_by:
                created_by = User.objects.filter(username="system").first()
            if not created_by:
                created_by = User.objects.create_user(username="system", email="system@example.com")
            self.created_by = created_by
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_item} <- {self.get_source_type_display()} ({self.quantity})"

    @property
    def reservation(self) -> SourcingAllocationSource:
        """
        Polymorphically retrieve the underlying reservation/shortage record.
        """
        if self.source_type == self.SourceType.STOCK:
            return self.physical_reservation
        elif self.source_type == self.SourceType.ARRIVAL:
            return self.arrival_reservation
        elif self.source_type == self.SourceType.SHORTAGE:
            return self.shortage
        return None

    def release(self, user=None):
        """
        Release the underlying reservation or shortage record, and soft-delete this allocation.
        """
        res = self.reservation
        if res:
            res.release(user=user)
        self.delete(user=user)
