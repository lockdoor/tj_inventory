import pytest
from datetime import date
from django.contrib.auth import get_user_model
from inventory.models import Warehouse, Stock, InventoryMovement, InventoryMovementItem, StockCard
from catalog.models import Item, Category

User = get_user_model()

@pytest.mark.django_db
class TestStockCardModel:
    """
    Unit tests for the StockCard model.
    """

    @pytest.fixture
    def user(self):
        """Standard user for audit fields."""
        return User.objects.create_user(username='testuser', password='password')

    @pytest.fixture
    def warehouse(self, user):
        """Standard warehouse."""
        return Warehouse.objects.create(name="Central", code="W-C", created_by=user)

    @pytest.fixture
    def category(self, user):
        """Standard category."""
        return Category.objects.create(name="Parts", code="P-01", created_by=user)

    @pytest.fixture
    def item(self, user, category):
        """Standard item."""
        return Item.objects.create(
            sku="SKU-999", name="Gear", unit="pcs", category=category, created_by=user
        )

    @pytest.fixture
    def stock(self, user, warehouse, item):
        """Standard stock balance."""
        return Stock.objects.create(
            warehouse=warehouse, item=item, lot_number="LOT-999", balance=100, created_by=user
        )

    @pytest.fixture
    def movement(self, user, warehouse):
        """Standard movement header."""
        return InventoryMovement.objects.create(
            document_no="MOV-100", type='inbound', date=date.today(), warehouse=warehouse, created_by=user
        )

    @pytest.fixture
    def movement_item(self, movement, item):
        """Standard movement line."""
        return InventoryMovementItem.objects.create(
            movement=movement, item=item, lot_number="LOT-999", quantity=50
        )

    def test_stockcard_creation(self, user, stock, movement_item):
        """Verify that a stockcard record can be created."""
        card = StockCard.objects.create(
            stock=stock,
            warehouse=stock.warehouse,
            item=stock.item,
            lot_number=stock.lot_number,
            movement_item=movement_item,
            qty_in=50.00,
            qty_out=0.00,
            note="Initial Stock In",
            created_by=user
        )
        assert card.stock == stock
        assert card.qty_in == 50.00
        assert card.lot_number == "LOT-999"
        assert card.created_by == user
        assert str(card).find("LOT-999") != -1

    def test_stockcard_reversibility(self, user, stock, movement_item):
        """Verify that stockcard allows reverse mapping."""
        StockCard.objects.create(
            stock=stock,
            warehouse=stock.warehouse,
            item=stock.item,
            lot_number=stock.lot_number,
            movement_item=movement_item,
            qty_in=25,
            created_by=user
        )
        assert stock.stock_cards.count() == 1
        assert movement_item.stock_cards.count() == 1
