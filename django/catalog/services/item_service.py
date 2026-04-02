"""
Item Service

Business logic for Item operations in the catalog.
Handles rules for product management, filtering, and soft-deletion.
"""

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
    def create(*, sku, name, unit, user, category=None, express_sku='', note='', status=Item.Status.ACTIVE, image=None):
        """
        Create a new item.
        If an image is provided, process it and set as the main image.
        """
        item = Item(
            sku=sku,
            name=name,
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
            processed_image = ItemService._process_item_image(image)
            ItemImage.objects.create(
                item=item,
                image=processed_image,
                is_main=True,
                created_by=user,
                status=ItemImage.Status.ACTIVE
            )

        return item

    @staticmethod
    def _process_item_image(image_file):
        """
        Process uploaded item image:
        1. Center crop to 1:1 square ratio
        2. Resize to 400x400 if larger than 400px
        3. Keep original size but still square if smaller than 400px
        """
        img = Image.open(image_file)
        
        # Convert to RGB (handles RGBA -> RGB)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        width, height = img.size
        size = min(width, height)

        # Center crop to square
        left = (width - size) // 2
        top = (height - size) // 2
        right = (width + size) // 2
        bottom = (height + size) // 2
        img = img.crop((left, top, right, bottom))

        # Scaling: max 400px
        if size > 400:
            img = img.resize((400, 400), Image.LANCZOS)
        
        # Save to buffer
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=90)
        
        # Return as Django ContentFile
        # The filename will be SKU-UUID.jpg (handled by item_image_upload_path)
        # But we pass the original basename with .jpg extension to pilot the extension
        import os
        base_name = os.path.splitext(image_file.name)[0]
        return ContentFile(buffer.getvalue(), name=f"{base_name}.jpg")

    @staticmethod
    def update(item, *, user, **fields):
        """
        Update an existing item.
        """
        allowed_fields = {'name', 'sku', 'express_sku', 'unit', 'category', 'note', 'status'}
        for field, value in fields.items():
            if field in allowed_fields:
                setattr(item, field, value)

        item.updated_by = user
        item.full_clean()
        item.save()
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
        item.is_deleted = False
        item.deleted_at = None
        item.deleted_by = None
        item.updated_by = user
        item.save()
        return item
