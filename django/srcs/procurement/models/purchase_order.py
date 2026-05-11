from django.db import models
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
