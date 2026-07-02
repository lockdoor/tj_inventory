from django.core.exceptions import ValidationError
from petty_cash.models import PettyCashCategory


class PettyCashCategoryService:
    @staticmethod
    def create_category(*, code, name, company, created_by, note=''):
        """
        Create a new PettyCashCategory.
        """
        category = PettyCashCategory(
            code=code,
            name=name,
            company=company,
            created_by=created_by,
            note=note
        )
        category.full_clean()
        category.save()
        return category

    @staticmethod
    def update_category(category, *, updated_by, **fields):
        """
        Update an existing PettyCashCategory.
        """
        allowed_fields = {'code', 'name', 'note'}
        for field, value in fields.items():
            if field in allowed_fields:
                setattr(category, field, value)
        category.updated_by = updated_by
        category.full_clean()
        category.save()
        return category

    @staticmethod
    def soft_delete_category(category, *, user):
        """
        Soft-delete a PettyCashCategory.
        """
        # Ensure it's not referenced by active payment items
        if category.payment_items.filter(payment__is_deleted=False).exists():
            raise ValidationError("Cannot delete category because it is referenced by active payment items.")
        category.delete(user=user)

    @staticmethod
    def restore_category(category, *, user):
        """
        Restore a soft-deleted PettyCashCategory.
        """
        category.restore(user=user)
        return category
