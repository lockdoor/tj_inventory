from django.db import models
from common.mixins.auditable import AuditableMixin
from common.mixins.status import StatusMixin

class Partner(AuditableMixin, StatusMixin):
    """
    Represents an external entity (Supplier, Customer, or both).
    """
    name = models.CharField(
        max_length=200, 
        unique=True, 
        help_text="Partner display name"
    )
    
    code = models.CharField(
        max_length=50, 
        unique=True, 
        help_text="Unique partner code (e.g. VEND001, CUST001)"
    )
    
    is_supplier = models.BooleanField(
        default=False, 
        help_text="Indicates if the partner is a supplier"
    )

    is_customer = models.BooleanField(
        default=False, 
        help_text="Indicates if the partner is a customer"
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
        help_text="Full address details"
    )
    
    contact_name = models.CharField(
        max_length=100, 
        blank=True, 
        default='', 
        help_text="Main contact person"
    )

    phone = models.CharField(
        max_length=50, 
        blank=True, 
        default='', 
        help_text="Contact phone number"
    )
    
    email = models.EmailField(
        blank=True, 
        default='', 
        help_text="Contact email address"
    )
    
    note = models.TextField(
        blank=True, 
        default='', 
        help_text="Internal notes"
    )

    class Meta:
        ordering = ['name']
        verbose_name = "Partner"
        verbose_name_plural = "Partners"
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        """Normalize fields before saving."""
        if self.name:
            self.name = self.name.strip()
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)
