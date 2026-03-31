"""
Category Model

Represents product categories with support for nested (parent-child)
hierarchy. Uses AuditableMixin for tracking and StatusMixin for
active/inactive lifecycle.
"""

from django.db import models
from common.mixins import AuditableMixin, StatusMixin


class Category(AuditableMixin, StatusMixin):
    """
    Product category with self-referencing parent for nested hierarchy.

    Examples:
        - Electronics (parent=None)
          └── Smartphones (parent=Electronics)
              └── Android (parent=Smartphones)
    """

    name = models.CharField(
        max_length=200,
        help_text="Category display name"
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique category code for internal reference"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='children',
        help_text="Parent category for nesting (null = top-level)"
    )
    note = models.TextField(
        blank=True,
        default='',
        help_text="Optional notes about this category"
    )

    class Meta:
        verbose_name_plural = "categories"
        ordering = ['name']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def is_root(self):
        """Check if this is a top-level category (no parent)."""
        return self.parent is None

    @property
    def full_path(self):
        """Return the full category path (e.g. 'Electronics > Smartphones > Android')."""
        parts = []
        current = self
        while current is not None:
            parts.append(current.name)
            current = current.parent
        return ' > '.join(reversed(parts))
