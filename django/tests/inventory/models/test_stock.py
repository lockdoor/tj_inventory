import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from inventory.models import Warehouse, Stock
from catalog.models import Item, Category

User = get_user_model()

@pytest.mark.django_db
class TestStockModel:
    """
    Unit tests for the Stock model.
    """

    @pytest.fixture
    def user(self):
        """Standard user for audit fields."""
        return User.objects.create_user(username='testuser', password='password')

    @pytest.fixture
    def warehouse(self, user):
        """Standard warehouse."""
        return Warehouse.objects.create(
            name="Main Hub",
            code="WH-MAIN",
            created_by=user
        )

    @pytest.fixture
    def category(self, user):
        """Standard category."""
        return Category.objects.create(
            name="Electronics",
            code="ELEC",
            created_by=user
        )

    @pytest.fixture
    def item(self, user, category):
        """Standard item."""
        return Item.objects.create(
            sku="SKU-001",
            name="Laptop",
            unit="pcs",
            category=category,
            created_by=user
        )

    def test_stock_creation(self, user, warehouse, item):
        """Verify that stock can be created with required fields."""
        stock = Stock.objects.create(
            warehouse=warehouse,
            item=item,
            lot_number="LOT-001",
            balance=100.50,
            created_by=user
        )
        # Decimal formatting may trim trailing zeros on __str__
        assert str(stock) == "LOT-001 (SKU-001): 100.5"
        assert stock.lot_number == "LOT-001"
        assert stock.balance == 100.50
        assert stock.warehouse == warehouse
        assert stock.item == item

    def test_lot_number_normalization(self, user, warehouse, item):
        """Verify that lot_number is normalized to uppercase and stripped."""
        stock = Stock.objects.create(
            warehouse=warehouse,
            item=item,
            lot_number="  lot-999  ",
            balance=50,
            created_by=user
        )
        assert stock.lot_number == "LOT-999"

    def test_global_lot_uniqueness(self, user, warehouse, item):
        """Verify that lot_number is unique across all items and warehouses."""
        Stock.objects.create(
            warehouse=warehouse,
            item=item,
            lot_number="UNIQUE-BATCH",
            balance=10,
            created_by=user
        )
        with pytest.raises(IntegrityError):
            Stock.objects.create(
                warehouse=warehouse,
                item=item,
                lot_number="UNIQUE-BATCH", # Duplicate
                balance=20,
                created_by=user
            )

    def test_stock_dates(self, user, warehouse, item):
        """Verify that mfg and exp dates are stored correctly."""
        from datetime import date
        stock = Stock.objects.create(
            warehouse=warehouse,
            item=item,
            lot_number="DATED-LOT",
            balance=5,
            mfg_date=date(2024, 1, 1),
            exp_date=date(2025, 1, 1),
            created_by=user
        )
        assert stock.mfg_date == date(2024, 1, 1)
        assert stock.exp_date == date(2025, 1, 1)

    def test_audit_fields(self, user, warehouse, item):
        """Verify that audit mixin tracks creation metadata."""
        stock = Stock.objects.create(
            warehouse=warehouse,
            item=item,
            lot_number="AUDIT-LOT",
            balance=1,
            created_by=user
        )
        assert stock.created_by == user
        assert stock.created_at is not None
