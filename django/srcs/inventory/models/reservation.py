from django.db import models
from common.mixins import AuditableMixin


class StockReservation(AuditableMixin):
    """
    Physical Hold ledger for Actual Stock.
    Warehouse Admin uses this to know which physical lots are locked.
    """
    class ReferenceType(models.TextChoices):
        SALES_ORDER = 'sales_order', 'Sales Order'
        PRODUCTION = 'production', 'Production'
        INTERNAL = 'internal', 'Internal Transfer'
        HOLD = 'hold', 'Quality/Maintenance Hold'
        ARRIVAL = 'arrival', 'Arrival Allocation'

    class ReservationStatus(models.TextChoices):
        RESERVED = 'reserved', 'Reserved'
        COMPLETED = 'completed', 'Completed'
        RELEASED = 'released', 'Released'

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
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='physical_reservations'
    )
    
    # Lineage Ancestry (Optional)
    origin_arrival_item = models.ForeignKey(
        'procurement.ArrivalItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='physical_reservations',
        help_text="The incoming shipment line that fulfilled this physical reservation hold"
    )
    
    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.RESERVED,
        help_text="Current lifecycle state of the reservation"
    )
    
    note = models.TextField(blank=True, default='')


    class Meta:
        verbose_name = "Stock Reservation"
        verbose_name_plural = "Stock Reservations"
        ordering = ['-created_at']

    def __str__(self):
        return f"HOLD ({self.status}): {self.reference_display_name} | {self.stock.lot_number} ({self.quantity})"

    @property
    def reference_display_name(self) -> str:
        """
        Returns a human-readable display name for the reference.
        If it's a sales order, tries to resolve the document number using the database ID.
        Otherwise, returns the raw reference_no.
        """
        if self.reference_type == self.ReferenceType.SALES_ORDER and self.reference_no:
            from sales.models import SalesOrder
            try:
                if not hasattr(self, '_cached_sales_order'):
                    self._cached_sales_order = SalesOrder.objects.filter(id=int(self.reference_no)).first()
                if self._cached_sales_order:
                    return self._cached_sales_order.document_no
            except (ValueError, TypeError):
                pass
        return self.reference_no

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
        Returns the quantity held for this physical stock reservation.
        """
        return self.quantity

    @property
    def document_reference(self):
        """
        Duck-type property satisfying SourcingAllocationSource.
        Returns the reference sales order or demand document number.
        """
        return self.reference_display_name

    @property
    def source_item(self):
        """
        Duck-type property satisfying SourcingAllocationSource.
        Returns the specific catalog item associated with the reserved stock lot.
        """
        return self.stock.item

    def release(self, user=None):
        """
        Duck-type method satisfying SourcingAllocationSource.
        Delegates to ReservationService to release the physical reservation.
        """
        from inventory.services.reservation_service import ReservationService
        return ReservationService.release(self, user=user)


from django.db.models.signals import post_delete
from django.dispatch import receiver

@receiver(post_delete, sender=StockReservation)
def sync_stock_reserved_qty_on_reservation_delete(sender, instance, **kwargs):
    """
    Ensure the associated Stock lot's reserved_qty is recalculated and
    synchronized when a StockReservation is physically deleted from the database.
    """
    from inventory.services.reservation_service import ReservationService
    try:
        ReservationService._sync_stock_reserved_qty(instance.stock)
    except Exception:
        # Protect against cascading deletions where the Stock lot itself is deleted
        pass
