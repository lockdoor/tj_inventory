from django.db import models
from common.mixins import AuditableMixin, StatusMixin

class Warehouse(AuditableMixin, StatusMixin):
    """
    Physical storage location for inventory.
    """
    name = models.CharField(
        max_length=100, 
        help_text="Warehouse display name"
    )
    code = models.CharField(
        max_length=20, 
        unique=True, 
        db_index=True,
        help_text="Unique warehouse code (e.g. WH-001)"
    )
    company = models.ForeignKey(
        'common.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='warehouses',
        help_text="The company this warehouse belongs to"
    )
    note = models.TextField(
        blank=True, 
        default='', 
        help_text="Internal notes about this warehouse"
    )

    class Meta:
        ordering = ['code']
        verbose_name = "Warehouse"
        verbose_name_plural = "Warehouses"
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        """Normalize fields before saving."""
        if self.code:
            self.code = self.code.strip().upper()
        if self.name:
            self.name = self.name.strip()
        super().save(*args, **kwargs)
