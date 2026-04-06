import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from inventory.models import Warehouse, Stock
from inventory.services import WarehouseService
from catalog.models import Item, Category

User = get_user_model()

@pytest.mark.django_db
class TestWarehouseService:
    """
    Unit tests for the WarehouseService.
    """

    @pytest.fixture
    def user(self):
        """Standard user for audit fields."""
        return User.objects.create_user(username='testuser', password='password')

    @pytest.fixture
    def category(self, user):
        """Standard category."""
        return Category.objects.create(name="Parts", code="P-01", created_by=user)

    @pytest.fixture
    def item(self, user, category):
        """Standard item."""
        return Item.objects.create(
            sku="SKU-888", name="Gear", unit="pcs", category=category, created_by=user
        )

    def test_create_warehouse(self, user):
        """Verify that a warehouse can be created through the service."""
        warehouse = WarehouseService.create(
            name="Main Hub",
            code="WH-MAIN",
            user=user,
            note="Primary storage"
        )
        assert warehouse.name == "Main Hub"
        assert warehouse.code == "WH-MAIN"
        assert warehouse.status == "active"
        assert warehouse.created_by == user

    def test_deactivate_warehouse_with_stock_fails(self, user, item):
        """Verify that deactivating a warehouse with active stock balance raises ValidationError."""
        warehouse = WarehouseService.create(name="Stocked WH", code="WH-STK", user=user)
        
        # Add stock balance
        Stock.objects.create(
            warehouse=warehouse,
            item=item,
            lot_number="LOT-001",
            balance=10.00,
            created_by=user
        )
        
        with pytest.raises(ValidationError) as exc_info:
            WarehouseService.update(warehouse, user=user, status='inactive')
        
        assert "Cannot deactivate warehouse" in str(exc_info.value)
        assert "active stock balances" in str(exc_info.value)

    def test_delete_warehouse_with_history_fails(self, user, item):
        """Verify that deleting a warehouse with historical stock records raises ValidationError."""
        warehouse = WarehouseService.create(name="Historical WH", code="WH-HIST", user=user)
        
        # Add a stock record (even with 0 balance)
        Stock.objects.create(
            warehouse=warehouse,
            item=item,
            lot_number="LOT-999",
            balance=0.00,
            created_by=user
        )
        
        with pytest.raises(ValidationError) as exc_info:
            WarehouseService.soft_delete(warehouse, user=user)
        
        assert "Cannot delete warehouse" in str(exc_info.value)
        assert "historical stock records" in str(exc_info.value)

    def test_soft_delete_and_restore(self, user):
        """Verify that a warehouse can be soft-deleted and restored if it has no stock."""
        warehouse = WarehouseService.create(name="Empty WH", code="WH-EMPTY", user=user)
        
        # Soft delete
        WarehouseService.soft_delete(warehouse, user=user)
        assert warehouse.is_deleted is True
        
        # Restore
        WarehouseService.restore(warehouse, user=user)
        assert warehouse.is_deleted is False
        assert warehouse.deleted_at is None
