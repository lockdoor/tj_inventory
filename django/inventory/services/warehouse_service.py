"""
Warehouse Service

Business logic for Warehouse operations.
Handles rules that go beyond simple data integrity.
"""

from django.core.exceptions import ValidationError
from inventory.models import Warehouse, Stock


class WarehouseService:

    @staticmethod
    def get_queryable_queryset():
        """
        Return a base queryset of non-deleted warehouses.
        Used by views to ensure soft-deleted records are excluded.
        """
        return Warehouse.objects.filter(is_deleted=False)

    @staticmethod
    def list_active():
        """
        Return all active (non-deleted) warehouses ordered by code.
        """
        return WarehouseService.get_queryable_queryset().filter(status='active').order_by('code')

    @staticmethod
    def create(*, name, code, user, note='', status='active'):
        """
        Create a new warehouse.
        """
        warehouse = Warehouse(
            name=name,
            code=code,
            note=note,
            status=status,
            created_by=user,
        )
        warehouse.full_clean()
        warehouse.save()
        return warehouse

    @staticmethod
    def update(warehouse, *, user, **fields):
        """
        Update an existing warehouse.

        Args:
            warehouse: Warehouse instance to update.
            user: The user performing the action.
            **fields: Fields to update (name, code, note, status).
        """
        allowed_fields = {'name', 'code', 'note', 'status'}
        
        # Rule: Cannot deactivate if it has active stock records with balance > 0
        if fields.get('status') == 'inactive' and warehouse.status == 'active':
            active_stock = Stock.objects.filter(warehouse=warehouse, balance__gt=0)
            if active_stock.exists():
                raise ValidationError(
                    f"Cannot deactivate warehouse '{warehouse.name}' because it still has "
                    f"{active_stock.count()} active stock balances. Please empty the warehouse first."
                )

        for field, value in fields.items():
            if field in allowed_fields:
                setattr(warehouse, field, value)

        warehouse.updated_by = user
        warehouse.full_clean()
        warehouse.save()
        return warehouse

    @staticmethod
    def soft_delete(warehouse, *, user):
        """
        Soft-delete a warehouse.

        Rules:
        - Cannot delete if it has any associated stock records (audit integrity).
        """
        # Rule: Cannot delete if it has ANY associated stock records
        if Stock.objects.filter(warehouse=warehouse).exists():
            raise ValidationError(
                f"Cannot delete warehouse '{warehouse.name}' because it has historical stock records. "
                f"Please consider deactivating it instead."
            )

        warehouse.delete(user=user)

    @staticmethod
    def restore(warehouse, *, user):
        """
        Restore a soft-deleted warehouse.
        """
        warehouse.is_deleted = False
        warehouse.deleted_at = None
        warehouse.deleted_by = None
        warehouse.updated_by = user
        warehouse.save()
        return warehouse
