from django.db import models
from common.mixins import AuditableMixin


class ArrivalReservation(AuditableMixin):
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

    class ReservationStatus(models.TextChoices):
        RESERVED = 'reserved', 'Reserved'
        CANCELLED = 'cancelled', 'Cancelled'
        PROMOTED = 'promoted', 'Promoted'

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
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='arrival_reservations'
    )

    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.RESERVED,
        help_text="Current lifecycle state of the reservation"
    )

    promoted_stock_reservation = models.ForeignKey(
        'inventory.StockReservation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='arrival_sources',
        help_text="The physical stock reservation created when this arrival line was received"
    )
    
    note = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = "Arrival Reservation"
        verbose_name_plural = "Arrival Reservations"
        ordering = ['-created_at']

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
        return f"PRE-SOLD: {self.reference_display_name} | {self.arrival_item} ({self.quantity})"

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
        Returns the quantity pre-sold/reserved from the expected arrival.
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
        Returns the catalog item associated with the arrival line.
        """
        return self.arrival_item.item

    def release(self, user=None):
        """
        Duck-type method satisfying SourcingAllocationSource.
        Delegates to ArrivalReservationService to release the arrival commitment.
        """
        from procurement.services.reservation_service import ArrivalReservationService
        return ArrivalReservationService.release(self, user=user)
