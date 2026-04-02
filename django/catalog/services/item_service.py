"""
Item Service

Business logic for Item operations in the catalog.
Handles rules for product management, filtering, and soft-deletion.
"""

from django.core.exceptions import ValidationError
from catalog.models import Item


class ItemService:

    @staticmethod
    def get_active_queryset():
        """
        Return a base queryset of non-deleted items.
        Includes select_related for performance when accessing categories.
        """
        return Item.objects.filter(is_deleted=False).select_related('category')

    @staticmethod
    def list_active():
        """
        Return all active items ordered by SKU.
        """
        return ItemService.get_active_queryset().order_by('sku')

    @staticmethod
    def create(*, sku, name, unit, user, category=None, express_sku='', note='', status=Item.Status.ACTIVE):
        """
        Create a new item.
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
        return item

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
