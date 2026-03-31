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
