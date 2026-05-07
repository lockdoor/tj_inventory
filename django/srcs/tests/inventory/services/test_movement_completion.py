import pytest
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from inventory.models import InventoryMovement, InventoryMovementItem, Stock, StockCard
from inventory.services import MovementService, WarehouseService
from catalog.models import Item, Category

User = get_user_model()

@pytest.mark.django_db
class TestMovementCompletion:
    """
    Unit tests for completion and reversal business logic.
    """

    @pytest.fixture
    def user(self):
        """Standard user for audit fields."""
        return User.objects.create_user(username='testuser', password='password')

    @pytest.fixture
    def warehouse(self, user):
        """Standard warehouse via service."""
        return WarehouseService.create(name="Completion Hub", code="WH-COMP", user=user)

    @pytest.fixture
    def item(self, user):
        """Standard item with category."""
        cat = Category.objects.create(name="Parts", code="P-COMP", created_by=user)
        return Item.objects.create(sku="SKU-COMP", name="Part X", unit="pcs", category=cat, created_by=user)

    def test_inbound_completion_with_multiple_same_lots_should_error(self, user, warehouse, item):
        """Error should happen when adding same lot number to the same movement."""
        movement = MovementService.create_movement(
            document_no="INC-001", type='inbound', date=date.today(), warehouse=warehouse, user=user
        )
        MovementService.add_item(movement, item=item, lot_number="LOT-SAME", quantity=50, user=user)
        with pytest.raises(ValidationError) as e:
            MovementService.add_item(movement, item=item, lot_number="LOT-SAME", quantity=50, user=user)
        assert "Item and lot number already exists in movement" in str(e.value)

    def test_outbound_completion_allows_negative_balance(self, user, warehouse, item):
        """Verify that outbound movements can result in a negative stock balance."""
        # 1. Setup existing stock (100 units)
        Stock.objects.create(warehouse=warehouse, item=item, lot_number="LOT-OUT", balance=Decimal('100.00'), created_by=user)
        
        # 2. Create outbound draft for 150 units (should NOW succeed)
        mov_out = MovementService.create_movement(
            document_no="OUT-NEG", type='outbound', date=date.today(), warehouse=warehouse, user=user
        )
        MovementService.add_item(mov_out, item=item, lot_number="LOT-OUT", quantity=150, user=user)
        
        # Act: Complete
        MovementService.complete_movement(mov_out, user=user)
        
        # Assert: Stock balance should be -50.00
        stock = Stock.objects.get(warehouse=warehouse, item=item, lot_number="LOT-OUT")
        assert stock.balance == Decimal('-50.00')
        
        # Assert: StockCard recorded correctly
        card = StockCard.objects.get(stock=stock, quantity=150, type=StockCard.StockCardType.OUT)
        assert "[COMPLETION]" in card.note

    def test_reversion_to_draft_allows_negative_balance(self, user, warehouse, item):
        """Verify that reverting an inbound can proceed even if it results in a negative balance."""
        # 1. Complete an Inbound movement (10 units)
        mov_in = MovementService.create_movement(
            document_no="REV-02", type='inbound', date=date.today(), warehouse=warehouse, user=user
        )
        MovementService.add_item(mov_in, item=item, lot_number="LOT-REV", quantity=10, user=user)
        MovementService.complete_movement(mov_in, user=user)
        
        stock = Stock.objects.get(warehouse=warehouse, item=item, lot_number="LOT-REV")
        assert stock.balance == 10.00
        
        # 2. Simulate partial use: Deduct 5 units manually (simulating another outbound movement)
        stock.balance -= Decimal('5.00')
        stock.save()
        
        # 3. Revert the 10-unit inbound (should NOW succeed, resulting in 5 - 10 = -5)
        MovementService.revert_to_draft(mov_in, user=user)
        
        assert mov_in.status == InventoryMovement.Status.DRAFT
        stock.refresh_from_db()
        assert stock.balance == Decimal('-5.00')
        
        # Verify Reversal StockCard
        rev_card = StockCard.objects.filter(stock=stock, note__contains="[REVERSION]").first()
        assert rev_card.quantity == 10
        assert rev_card.type == StockCard.StockCardType.OUT # Inverted Inbound remains Qty Out
