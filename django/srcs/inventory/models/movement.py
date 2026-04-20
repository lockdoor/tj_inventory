from django.db import models
from common.mixins import AuditableMixin, StatusMixin

class InventoryMovement(AuditableMixin, StatusMixin):
    """
    Header record for a warehouse movement document.
    """
    class MovementType(models.TextChoices):
        INBOUND = 'inbound', 'Inbound'
        OUTBOUND = 'outbound', 'Outbound'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        COMPLETED = 'completed', 'Completed'

    class ReferenceType(models.TextChoices):
        NONE = 'none', 'None'
        PRODUCTION = 'production', 'Production Order'
        STOCK_ARRIVAL = 'stock_arrival', 'Stock Arrival Schedule'
        OTHER = 'other', 'Other'

    document_no = models.CharField(
        max_length=50, 
        unique=True, 
        db_index=True,
        help_text="Unique document number (Manual or Auto)"
    )
    type = models.CharField(
        max_length=20, 
        choices=MovementType.choices,
        help_text="Movement direction"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        help_text="Document lifecycle status"
    )
    date = models.DateField(
        help_text="Transaction date"
    )
    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.CASCADE,
        related_name='movements',
        help_text="Primary warehouse for this movement"
    )
    partner = models.ForeignKey(
        'partners.Partner',
        on_delete=models.SET_NULL,
        null=True, 
        blank=True,
        related_name='movements',
        help_text="External partner (Supplier/Customer) involved"
    )
    note = models.TextField(
        blank=True, 
        default='', 
        help_text="General notes about this document"
    )
    recipient = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Recipient name (fallback for missing Partner records)"
    )

    reference_type = models.CharField(
        max_length=50,
        choices=ReferenceType.choices,
        default=ReferenceType.NONE,
        blank=True,
        help_text="External document category"
    )
    reference_no = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="ID/Number of the source document"
    )

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Inventory Movement"
        verbose_name_plural = "Inventory Movements"

    def __str__(self):
        return f"{self.document_no} ({self.get_type_display()})"


class InventoryMovementItem(models.Model):
    """
    Individual items (lines) within a movement document.
    Captures batch details during the draft phase.
    """
    movement = models.ForeignKey(
        InventoryMovement,
        on_delete=models.CASCADE,
        related_name='items'
    )
    item = models.ForeignKey(
        'catalog.Item',
        on_delete=models.CASCADE,
        related_name='movement_items'
    )
    lot_number = models.CharField(
        max_length=100, 
        help_text="Batch/Lot number recorded at entry"
    )
    quantity = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        help_text="Quantity moved"
    )
    unit_cost = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Unit cost at the time of movement"
    )
    mfg_date = models.DateField(
        null=True, 
        blank=True, 
        help_text="Manufacturing Date (Draft phase entry)"
    )
    exp_date = models.DateField(
        null=True, 
        blank=True, 
        help_text="Expiry Date (Draft phase entry)"
    )
    note = models.TextField(
        blank=True, 
        default=''
    )

    class Meta:
        verbose_name = "Movement Item"
        verbose_name_plural = "Movement Items"

    def __str__(self):
        return f"{self.movement.document_no} - {self.item.sku} ({self.quantity})"
