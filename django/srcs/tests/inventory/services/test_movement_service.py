import pytest
from datetime import date
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from inventory.models import InventoryMovement, InventoryMovementItem, InventoryMovementAttachment, Warehouse
from inventory.services import MovementService
from catalog.models import Item, Category

User = get_user_model()

@pytest.mark.django_db
class TestMovementService:
    """
    Unit tests for the MovementService.
    """

    @pytest.fixture
    def user(self):
        """Standard user for audit fields."""
        return User.objects.create_user(username='testuser', password='password')

    @pytest.fixture
    def warehouse(self, user):
        """Standard warehouse."""
        from inventory.services import WarehouseService
        return WarehouseService.create(name="Service Hub", code="WH-SRV", user=user)

    @pytest.fixture
    def category(self, user):
        """Standard category."""
        return Category.objects.create(name="Parts", code="P-02", created_by=user)

    @pytest.fixture
    def item(self, user, category):
        """Standard item."""
        return Item.objects.create(
            sku="SKU-SERV", name="Service Item", unit="pcs", category=category, created_by=user
        )

    def test_create_draft_movement(self, user, warehouse):
        """Verify that a movement can be created in draft status."""
        movement = MovementService.create_movement(
            document_no="DOC-001",
            type='inbound',
            date=date.today(),
            warehouse=warehouse,
            user=user,
            note="Testing draft creation"
        )
        assert movement.document_no == "DOC-001"
        assert movement.status == InventoryMovement.Status.DRAFT
        assert movement.created_by == user

    def test_add_item_to_draft(self, user, warehouse, item):
        """Verify that items can be added to a movement draft."""
        movement = MovementService.create_movement(
            document_no="DOC-002",
            type='inbound',
            date=date.today(),
            warehouse=warehouse,
            user=user
        )
        
        item_line = MovementService.add_item(
            movement,
            item=item,
            lot_number="LOT-ABC",
            quantity=100.00,
            user=user,
            mfg_date=date(2024, 1, 1),
            exp_date=date(2025, 1, 1)
        )
        
        assert item_line.movement == movement
        assert item_line.lot_number == "LOT-ABC"
        assert item_line.quantity == 100.00

    def test_update_item_in_draft(self, user, warehouse, item):
        """Verify that an item line can be updated in a draft."""
        movement = MovementService.create_movement(
            document_no="DOC-003",
            type='inbound',
            date=date.today(),
            warehouse=warehouse,
            user=user
        )
        item_line = MovementService.add_item(movement, item=item, lot_number="OLD-LOT", quantity=10, user=user)
        
        MovementService.update_item(item_line, user=user, lot_number="NEW-LOT", quantity=20)
        
        item_line.refresh_from_db()
        assert item_line.lot_number == "NEW-LOT"
        assert item_line.quantity == 20

    def test_modify_completed_document_fails(self, user, warehouse, item):
        """Verify that modifying a non-draft document raises ValidationError."""
        movement = MovementService.create_movement(
            document_no="DOC-004",
            type='inbound',
            date=date.today(),
            warehouse=warehouse,
            user=user
        )
        
        # Force set status to completed
        movement.status = InventoryMovement.Status.COMPLETED
        movement.save()
        
        with pytest.raises(ValidationError) as exc_info:
            MovementService.add_item(movement, item=item, lot_number="LOT-X", quantity=10, user=user)
        
        assert "Cannot modify document" in str(exc_info.value)
        assert "Completed" in str(exc_info.value)

    def test_draft_attachment_management(self, user, warehouse):
        """Verify that attachments can be added to a draft."""
        movement = MovementService.create_movement(
            document_no="DOC-005",
            type='inbound',
            date=date.today(),
            warehouse=warehouse,
            user=user
        )
        
        fake_file = SimpleUploadedFile("invoice.txt", b"content", content_type="text/plain")
        attachment = MovementService.add_attachment(movement, document_file=fake_file, user=user)
        
        assert attachment.movement == movement
        assert movement.attachments.count() == 1
        
        # Soft delete attachment
        MovementService.remove_attachment(attachment, user=user)
        assert attachment.is_deleted is True
        assert movement.attachments.filter(is_deleted=False).count() == 0

    def test_movement_item_quantity_can_be_negative(self, user, warehouse, item):
        """Verify that movement item quantity can be negative."""
        movement = MovementService.create_movement(
            document_no="DOC-006",
            type='outbound',
            date=date.today(),
            warehouse=warehouse,
            user=user
        )
        item_line = MovementService.add_item(
            movement,
            item=item,
            lot_number="LOT-ABC",
            quantity=-10,
            user=user
        )
        assert movement.status == InventoryMovement.Status.DRAFT
        assert item_line.quantity == -10
        MovementService.complete_movement(movement, user=user)
        item_line.refresh_from_db()
        assert item_line.quantity == -10
        assert movement.status == InventoryMovement.Status.COMPLETED

    def test_movement_update_can_remove_item_line(self, user, warehouse, item):
        """Verify that movement update can remove item line."""
        movement = MovementService.create_movement(
            document_no="DOC-007",
            type='outbound',
            date=date.today(),
            warehouse=warehouse,
            user=user
        )
        item_line_1 = MovementService.add_item(movement, item=item, lot_number="LOT-ABC", quantity=10, user=user)
        item_line_2 = MovementService.add_item(movement, item=item, lot_number="LOT-BCD", quantity=20, user=user)
        MovementService.complete_movement(movement, user=user)
        assert movement.status == InventoryMovement.Status.COMPLETED
        assert movement.items.count() == 2
        #change movement to draft
        MovementService.revert_to_draft(movement, user=user)
        assert movement.status == InventoryMovement.Status.DRAFT
        # remove item line
        MovementService.remove_item(item_line_1, user=user)
        assert movement.items.count() == 1
        MovementService.complete_movement(movement, user=user)
        assert movement.status == InventoryMovement.Status.COMPLETED
        assert movement.items.count() == 1

    def test_movement_same_item_lot_number_in_document_should_error(self, user, warehouse, item):
        """Verify that movement same item and lot number in document should error."""
        movement = MovementService.create_movement(
            document_no="DOC-008",
            type='outbound',
            date=date.today(),
            warehouse=warehouse,
            user=user
        )
        MovementService.add_item(movement, item=item, lot_number="LOT-ABC", quantity=10, user=user)
        with pytest.raises(ValidationError) as exc_info:
            MovementService.add_item(movement, item=item, lot_number="LOT-ABC", quantity=20, user=user)
        assert "Item and lot number already exists in movement" in str(exc_info.value)
        