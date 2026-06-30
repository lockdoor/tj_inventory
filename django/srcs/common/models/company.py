from django.db import models
from django.core.exceptions import ValidationError
from common.mixins import AuditableMixin, StatusMixin


class Company(AuditableMixin, StatusMixin):
    """
    Represents an internal legal entity/company.
    """
    name = models.CharField(
        max_length=200, 
        unique=True, 
        help_text="Company display name"
    )
    code = models.CharField(
        max_length=50, 
        unique=True, 
        help_text="Unique company code (e.g. TJ, TJG)"
    )
    express_database_name = models.CharField(
        max_length=50, 
        blank=True, 
        default='', 
        help_text="Express database name (e.g. TJ69, JINTAN68)"
    )
    tax_id = models.CharField(
        max_length=50, 
        blank=True, 
        default='', 
        help_text="Tax identification number"
    )
    address = models.TextField(
        blank=True, 
        default='', 
        help_text="Registered address"
    )
    phone = models.CharField(
        max_length=50, 
        blank=True, 
        default='', 
        help_text="Phone number"
    )
    email = models.EmailField(
        blank=True, 
        default='', 
        help_text="Email address"
    )
    note = models.TextField(
        blank=True, 
        default='', 
        help_text="Internal notes about this company"
    )

    class Meta:
        ordering = ['name']
        verbose_name = "Company"
        verbose_name_plural = "Companies"

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        """Normalize fields before saving."""
        if self.name:
            self.name = self.name.strip()
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)
