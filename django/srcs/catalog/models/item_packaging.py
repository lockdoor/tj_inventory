"""
ItemPackaging Model

Defines alternative packaging units (e.g., Carton, Box, Pallet) and their
conversion multipliers to the base unit (pieces).
"""

from django.db import models
from common.mixins import AuditableMixin, StatusMixin


class ItemPackaging(AuditableMixin, StatusMixin):
    """
    Alternative packaging unit for a catalog Item.
    Maps a packaging name to a quantity of the base unit.
    """

    item = models.ForeignKey(
        'catalog.Item',
        on_delete=models.CASCADE,
        related_name='packagings',
        help_text="The item this packaging belongs to"
    )
    name = models.CharField(
        max_length=50,
        help_text="Packaging name (e.g., Carton, Box, Dozen, Pallet)"
    )
    quantity = models.PositiveIntegerField(
        help_text="Number of base units (pieces) contained in this packaging"
    )
    barcode = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Optional barcode specific to this packaging unit"
    )
    note = models.TextField(
        blank=True,
        default='',
        help_text="Optional internal notes about this packaging"
    )

    class Meta:
        ordering = ['item', 'quantity']
        indexes = [
            models.Index(fields=['item', 'name']),
            models.Index(fields=['barcode']),
        ]

    def __str__(self):
        return f"{self.item.sku} - {self.name} ({self.quantity} pcs)"

    def save(self, *args, **kwargs):
        """Normalize fields before saving."""
        if self.name:
            self.name = self.name.strip()
        if self.barcode:
            self.barcode = self.barcode.strip()
        super().save(*args, **kwargs)
