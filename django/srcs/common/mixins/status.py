"""
Status Mixin

Provides a common active/inactive status field
for models that share this simple lifecycle pattern.
"""

from django.db import models


class StatusMixin(models.Model):
    """
    Abstract mixin that provides an active/inactive status field.

    Use this for models that share the same simple status pattern.
    For models with context-specific statuses (e.g. order lifecycle),
    define TextChoices directly on the model instead.
    """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        help_text="Record status (active/inactive)"
    )

    class Meta:
        abstract = True

    def activate(self):
        """Set status to active."""
        self.status = self.Status.ACTIVE
        self.save()

    def deactivate(self):
        """Set status to inactive."""
        self.status = self.Status.INACTIVE
        self.save()

    @property
    def is_active(self):
        """Check if the record is active."""
        return self.status == self.Status.ACTIVE
