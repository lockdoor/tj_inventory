"""
Item Model

Represents a product/item in the catalog. Each item belongs to a category
and has a unique SKU for internal tracking and an optional Express SKU
for syncing with the external Express system.
"""

from django.db import models
from common.mixins import AuditableMixin, StatusMixin


class Item(AuditableMixin, StatusMixin):
    """
    Product item in the inventory catalog.
    """

    category = models.ForeignKey(
        'catalog.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items',
        help_text="Category this item belongs to"
    )
    sku = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique internal SKU code"
    )
    express_sku = models.CharField(
        max_length=50,
        blank=True,
        default='',
        db_index=True,
        help_text="SKU code for Express system sync (optional)"
    )
    name = models.CharField(
        max_length=200,
        help_text="Item display name"
    )
    unit = models.CharField(
        max_length=50,
        help_text="Unit of measurement (e.g. pcs, kg, box)"
    )

    note = models.TextField(
        blank=True,
        default='',
        help_text="Internal notes about this item"
    )

    class Meta:
        ordering = ['sku']
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    def save(self, *args, **kwargs):
        """Normalize fields before saving."""
        if self.sku:
            self.sku = self.sku.strip()
        if self.name:
            self.name = self.name.strip()
        if self.unit:
            self.unit = self.unit.strip()
        super().save(*args, **kwargs)

    @property
    def has_main_image(self):
        """Check if this item has a main image."""
        return self.images.filter(is_main=True).exists()

    @property
    def main_image(self):
        """Get the main image, or the first image if no main is set."""
        return (
            self.images.filter(is_main=True).first()
            or self.images.first()
        )
