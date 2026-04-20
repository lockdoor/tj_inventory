"""
Audit Mixin

Provides common audit fields and optimistic locking functionality
for all models.
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords


class AuditableMixin(models.Model):
    """
    Abstract mixin that provides audit fields and optimistic locking.
    
    Includes:
    - created_at, created_by
    - updated_at, updated_by  
    - version (for optimistic locking)
    - history (simple history tracking)
    """
    
    # Audit fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when record was created"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='%(app_label)s_%(class)s_created',
        help_text="User who created this record"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when record was last updated"
    )
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='%(app_label)s_%(class)s_updated',
        help_text="User who last updated this record",
        null=True,
        blank=True
    )
    
    # Soft Delete fields
    is_deleted = models.BooleanField(
        default=False,
        help_text="Indicates if the record is soft-deleted"
    )
    deleted_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Timestamp when record was soft-deleted"
    )
    deleted_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='%(app_label)s_%(class)s_deleted',
        help_text="User who deleted this record",
        null=True,
        blank=True
    )
    
    # Optimistic locking
    version = models.PositiveIntegerField(
        default=1,
        help_text="Version number for optimistic locking"
    )
    
    # History tracking
    history = HistoricalRecords(inherit=True)
    
    class Meta:
        abstract = True
    
    def delete(self, user=None, *args, **kwargs):
        """Soft delete the record instead of physical deletion"""
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user:
            self.deleted_by = user
        self.save()
        
    def hard_delete(self, *args, **kwargs):
        """Perform an actual physical deletion"""
        super().delete(*args, **kwargs)
    
    def restore(self):
        """Restore a soft-deleted record"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()
    
    def save(self, *args, **kwargs):
        """Save with optimistic locking check"""
        if self.pk:
            self._check_optimistic_locking()
            self.version += 1
        
        super().save(*args, **kwargs)
    
    def _check_optimistic_locking(self):
        """Check if record has been modified by another user"""
        try:
            current = type(self).objects.get(pk=self.pk)
            if current.version != self.version:
                raise ValidationError(
                    "Record has been modified by another user. "
                    "Please refresh and try again."
                )
        except type(self).DoesNotExist:
            # Record was deleted, allow save as new
            pass
    
    def refresh_version(self):
        """Refresh version from database"""
        if self.pk:
            current = type(self).objects.get(pk=self.pk)
            self.version = current.version
            return self.version
        return None
