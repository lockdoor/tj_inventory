"""
ItemImage Model

Stores images for catalog items. Each item can have multiple images,
but only one can be marked as the main/primary image.
"""

import os
import uuid
from django.db import models
from common.mixins import AuditableMixin, StatusMixin


def item_image_upload_path(instance, filename):
    """
    Generate upload path: item_images/<sku>-<uuid8>.<ext>
    """
    ext = filename.split('.')[-1].lower()
    unique_id = uuid.uuid4().hex[:8]
    sku = instance.item.sku if instance.item else 'new'
    return os.path.join('item_images', f"{sku}-{unique_id}.{ext}")


class ItemImage(AuditableMixin, StatusMixin):
    """
    Image associated with a catalog Item.
    Only one image per item should be marked as is_main=True.
    """

    item = models.ForeignKey(
        'catalog.Item',
        on_delete=models.CASCADE,
        related_name='images',
        help_text="The item this image belongs to"
    )
    image = models.ImageField(
        upload_to=item_image_upload_path,
        help_text="Image file for the item"
    )
    is_main = models.BooleanField(
        default=False,
        help_text="Mark as the main/primary image for the item"
    )
    note = models.TextField(
        blank=True,
        default='',
        help_text="Optional caption or note for this image"
    )

    class Meta:
        ordering = ['-is_main', '-created_at']
        indexes = [
            models.Index(fields=['item', 'is_main']),
        ]

    def __str__(self):
        main_label = " (Main)" if self.is_main else ""
        return f"{self.item.sku} Image{main_label}"

    @property
    def filename(self):
        """Return just the filename without the path."""
        if self.image and self.image.name:
            return os.path.basename(self.image.name)
        return None

    @property
    def extension(self):
        """Return the file extension (e.g. '.jpg')."""
        if self.image and self.image.name:
            return os.path.splitext(self.image.name)[1].lower()
        return None
