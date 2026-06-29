"""
Item Service

Business logic for Item operations in the catalog.
Handles rules for product management, filtering, and soft-deletion.
"""

import os
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image
from io import BytesIO
from catalog.models import Item, ItemImage


class ItemService:

    @staticmethod
    def get_active_queryset():
        """
        Return a base queryset of non-deleted items.
        Includes select_related for performance when accessing categories and prefetch_related for images.
        """
        return Item.objects.filter(is_deleted=False).select_related('category').prefetch_related('images')

    @staticmethod
    def list_active():
        """
        Return all active items ordered by SKU.
        """
        return ItemService.get_active_queryset().order_by('sku')

    @staticmethod
    def list_deleted():
        """
        Return all soft-deleted items ordered by SKU.
        """
        return Item.objects.filter(is_deleted=True).select_related('category', 'deleted_by').prefetch_related('images').order_by('sku')

    @staticmethod
    def create(*, sku, name, unit, user, name2='', category=None, express_sku='', note='', status=Item.Status.ACTIVE, image=None):
        """
        Create a new item.
        If an image is provided, process it and set as the main image.
        """
        item = Item(
            sku=sku,
            name=name,
            name2=name2,
            unit=unit,
            category=category,
            express_sku=express_sku,
            note=note,
            status=status,
            created_by=user
        )
        item.full_clean()
        item.save()

        if image:
            ItemService.validate_file(image)
            ItemImage.objects.create(
                item=item,
                image=image,
                is_main=True,
                created_by=user,
                status=ItemImage.Status.ACTIVE
            )

        return item

    @staticmethod
    def validate_file(file):
        """
        Validate file size and type.
        Must be an image, and size < 10 MB.
        """
        limit = 10 * 1024 * 1024
        if file.size > limit:
            raise ValidationError("File size must not exceed 10 MB.")
        
        ext = os.path.splitext(file.name)[1].lower()
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        if ext not in allowed_extensions:
            raise ValidationError("Only image files (JPG, JPEG, PNG, WEBP, GIF) are allowed.")

    @staticmethod
    def update(item, *, user, **fields):
        """
        Update an existing item.
        """
        allowed_fields = {'name', 'name2', 'sku', 'express_sku', 'unit', 'category', 'note', 'status'}
        image = fields.pop('image', None)

        for field, value in fields.items():
            if field in allowed_fields:
                setattr(item, field, value)

        item.updated_by = user
        item.full_clean()
        item.save()

        if image:
            # If a new image is provided, validate it and set as the new main image
            ItemService.validate_file(image)
            
            # Deactivate previous main images
            item.images.filter(is_main=True).update(is_main=False)
            
            # Create new main image record
            ItemImage.objects.create(
                item=item,
                image=image,
                is_main=True,
                created_by=user,
                status=ItemImage.Status.ACTIVE
            )

        return item

    @staticmethod
    def soft_delete(item, *, user):
        """
        Soft-delete an item.
        """
        item.delete(user=user)

    @staticmethod
    def restore(item, *, user):
        """
        Restore a soft-deleted item.
        """
        item.restore(user=user)
        return item
