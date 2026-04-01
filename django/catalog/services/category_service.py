"""
Category Service

Business logic for Category operations.
Handles rules that go beyond simple data integrity.

Permission checks are NOT here — they belong in the View/API layer.
"""

from django.core.exceptions import ValidationError
from catalog.models import Category


class CategoryService:

    @staticmethod
    def get_active_queryset():
        """
        Return a base queryset of non-deleted categories.
        Used by views to ensure soft-deleted records are excluded.
        """
        return Category.objects.filter(is_deleted=False)

    @staticmethod
    def list_active():
        """
        Return all active (non-deleted) categories ordered by name.
        """
        return CategoryService.get_active_queryset().order_by('name')

    @staticmethod
    def list_deleted():
        """
        Return all soft-deleted categories ordered by name.
        """
        return Category.objects.filter(is_deleted=True).order_by('name')

    @staticmethod
    def create(*, name, code, user, parent=None, note=''):
        """
        Create a new category.

        Args:
            name: Category display name.
            code: Unique category code.
            user: The user performing the action.
            parent: Optional parent category for nesting.
            note: Optional notes.
        """
        category = Category(
            name=name,
            code=code,
            parent=parent,
            note=note,
            created_by=user,
        )
        category.full_clean()
        category.save()
        return category

    @staticmethod
    def update(category, *, user, **fields):
        """
        Update an existing category.

        Args:
            category: Category instance to update.
            user: The user performing the action.
            **fields: Fields to update (name, code, parent, note).
        """
        allowed_fields = {'name', 'code', 'parent', 'note'}
        for field, value in fields.items():
            if field in allowed_fields:
                setattr(category, field, value)

        category.updated_by = user
        category.full_clean()
        category.save()
        return category

    @staticmethod
    def soft_delete(category, *, user):
        """
        Soft-delete a category.

        Rules:
        - Cannot delete if it has active (non-deleted) children.

        Raises:
            ValidationError: If business rules are violated.
        """
        active_children = category.children.filter(is_deleted=False)
        if active_children.exists():
            child_names = list(active_children.values_list('name', flat=True))
            raise ValidationError(
                f"Cannot delete category '{category.name}' because it has "
                f"active children: {', '.join(child_names)}. "
                f"Please delete or reassign them first."
            )
        category.delete(user=user)

    @staticmethod
    def restore(category, *, user):
        """
        Restore a soft-deleted category.

        Rules:
        - If category has a parent, the parent MUST be active (non-deleted) 
          otherwise restoration is blocked to prevent orphaned records.

        Raises:
            ValidationError: If business rules are violated.
        """
        if category.parent and category.parent.is_deleted:
            raise ValidationError(
                f"Cannot restore category '{category.name}' because its parent "
                f"'{category.parent.name}' is still in the trash. "
                f"Please restore the parent first."
            )
        
        category.is_deleted = False
        category.deleted_at = None
        category.deleted_by = None
        category.updated_by = user
        category.save()
        return category
