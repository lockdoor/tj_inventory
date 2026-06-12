from django.db import models
from django.db.models import Sum, F
from common.mixins.auditable import AuditableMixin


class PurchaseOrder(AuditableMixin):
    """
    Represents a formal order to a supplier.
    """
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted'
        CLOSED = 'closed', 'Closed'
        CANCELLED = 'cancelled', 'Cancelled'

    document_no = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique purchase order number"
    )
    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        related_name='purchase_orders',
        help_text="Supplier for this order"
    )
    expected_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expected delivery date"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        help_text="Current status of the order"
    )
    note = models.TextField(
        blank=True,
        default='',
        help_text="Internal notes about this order"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Purchase Order"
        verbose_name_plural = "Purchase Orders"

    def __str__(self):
        return f"{self.document_no} ({self.partner.name})"

    @property
    def total_amount(self):
        """Calculate total amount of all items."""
        total = sum(item.subtotal for item in self.items.all())
        return total

    @property
    def is_sufficient(self):
        """Return True if all items have arrival pieces greater than or equal to order pieces."""
        for item in self.items.all():
            if item.arrival_pieces < item.order_pieces:
                return False
        return True


class PurchaseOrderItem(models.Model):
    """
    Individual item line in a Purchase Order.
    """
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        'catalog.Item',
        on_delete=models.PROTECT,
        related_name='purchase_order_items'
    )
    packaging = models.ForeignKey(
        'catalog.ItemPackaging',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_order_items',
        help_text="Ordered packaging container (optional)"
    )
    order_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Quantity ordered"
    )
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Agreed unit cost"
    )

    class Meta:
        verbose_name = "Purchase Order Item"
        verbose_name_plural = "Purchase Order Items"

    def __str__(self):
        return f"{self.purchase_order.document_no} - {self.item.sku} ({self.order_qty})"

    @property
    def subtotal(self):
        """Calculate subtotal for this line."""
        if self.order_qty and self.unit_cost:
            return self.order_qty * self.unit_cost
        return 0

    @property
    def arrival_qty(self):
        """Sum of expected arrival quantity across all active linked arrivals."""
        return self.arrival_items.filter(
            arrival__is_deleted=False
        ).exclude(
            arrival__status='cancelled'
        ).aggregate(total=models.Sum('expected_qty'))['total'] or 0

    @property
    def order_pieces(self):
        """Total ordered quantity in base pieces."""
        if self.packaging:
            return self.order_qty * self.packaging.quantity
        return self.order_qty

    @property
    def arrival_pieces(self):
        """Total expected arrival quantity in base pieces."""
        if self.packaging:
            return self.arrival_qty * self.packaging.quantity
        return self.arrival_qty
