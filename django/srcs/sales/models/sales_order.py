from django.db import models
from django.utils import timezone
from common.mixins import AuditableMixin


class SalesOrder(AuditableMixin):
    """
    Represents a customer order (Pre-order or Normal Sale).
    """
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PREORDER = 'preorder', 'Pre-order'
        CONFIRMED = 'confirmed', 'Confirmed'
        PROCESSING = 'processing', 'Processing'
        SHIPPED = 'shipped', 'Shipped'
        CANCELLED = 'cancelled', 'Cancelled'

    class OrderType(models.TextChoices):
        NORMAL = 'normal', 'Normal Sale'
        PREORDER = 'preorder', 'Pre-order'

    document_no = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="SO-XXXX unique number"
    )
    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.PROTECT,
        related_name='sales_orders',
        help_text="Customer record"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    order_type = models.CharField(
        max_length=20,
        choices=OrderType.choices,
        default=OrderType.NORMAL
    )
    order_date = models.DateField(
        default=timezone.now,
        help_text="Target timeline expected to fulfill the order"
    )
    note = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Sales Order"
        verbose_name_plural = "Sales Orders"

    def __str__(self):
        return f"{self.document_no} - {self.partner.name}"


class SalesOrderItem(models.Model):
    """
    Individual items within a Sales Order.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Allocation'
        PARTIAL = 'partial', 'Partially Allocated'
        ALLOCATED = 'allocated', 'Fully Allocated'
        SHIPPED = 'shipped', 'Shipped'
        CANCELLED = 'cancelled', 'Cancelled'

    order = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        'catalog.Item',
        on_delete=models.PROTECT,
        related_name='sales_items'
    )
    
    # Quantities
    requested_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Original quantity requested by customer"
    )
    allocated_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Total quantity allocated (Physical + Future + Shortage)"
    )
    fulfilled_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Quantity actually shipped from warehouse"
    )

    # Financials
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Selling price per unit"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    is_manual_allocate = models.BooleanField(
        default=False,
        help_text="Designates whether this item has been manually allocated, bypassing automatic stock sourcing (FEFO)"
    )

    class Meta:
        verbose_name = "Sales Order Item"
        verbose_name_plural = "Sales Order Items"

    @property
    def subtotal(self):
        return self.requested_qty * self.unit_price

    @property
    def has_manual_allocations(self):
        return self.is_manual_allocate

    @property
    def real_allocated_qty(self):
        from sales.models import SalesAllocation
        return self.allocations.exclude(
            source_type=SalesAllocation.SourceType.SHORTAGE
        ).aggregate(total=models.Sum('quantity'))['total'] or 0

    def __str__(self):
        return f"{self.order.document_no} - {self.item.sku} ({self.requested_qty})"
