from django.core.exceptions import ValidationError
from accounting.models import PettyCashCategory


class PettyCashCategoryService:
    @staticmethod
    def bulk_create_or_update_categories(*, categories_data, company, created_by):
        """
        Bulk create or update PettyCashCategory records for a specific company.
        categories_data: list of dicts: [{'code': '...', 'name': '...', 'note': '...'}]
        """
        if not categories_data:
            return []

        objs = []
        for item in categories_data:
            code = item['code'].strip().upper()
            name = item['name'].strip()
            note = item.get('note', '')
            obj = PettyCashCategory(
                code=code,
                name=name,
                company=company,
                created_by=created_by,
                note=note,
                is_deleted=False,
                deleted_at=None,
                deleted_by=None
            )
            objs.append(obj)

        return PettyCashCategory.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=['company', 'code'],
            update_fields=['name', 'note', 'is_deleted', 'deleted_at', 'deleted_by']
        )

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
