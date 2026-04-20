import pytest
from datetime import date
from django.contrib.auth import get_user_model
from inventory.models import Warehouse, InventoryMovement, InventoryMovementItem, InventoryMovementAttachment
from catalog.models import Item, Category

User = get_user_model()

@pytest.mark.django_db
class TestMovementModel:
    """
    Unit tests for Inventory Movement models.
    """

    @pytest.fixture
    def user(self):
        """Standard user for audit fields."""
        return User.objects.create_user(username='testuser', password='password')

    @pytest.fixture
    def warehouse(self, user):
        """Standard warehouse."""
        return Warehouse.objects.create(
            name="North Warehouse",
            code="WH-NORTH",
            created_by=user
        )

    @pytest.fixture
    def category(self, user):
        """Standard category."""
        return Category.objects.create(
            name="Hardware",
            code="HW",
            created_by=user
        )

    @pytest.fixture
    def item(self, user, category):
        """Standard item."""
        return Item.objects.create(
            sku="HW-001",
            name="Hammer",
            unit="pcs",
            category=category,
            created_by=user
        )

    def test_movement_header_creation(self, user, warehouse):
        """Verify that a movement header can be created."""
        movement = InventoryMovement.objects.create(
            document_no="MOV-2024-001",
            type=InventoryMovement.MovementType.INBOUND,
            date=date.today(),
            warehouse=warehouse,
            created_by=user
        )
        assert str(movement) == "MOV-2024-001 (Inbound)"
        assert movement.status == "draft" # override StatusMixin with draft, completed

    def test_movement_item_creation(self, user, warehouse, item):
        """Verify that movement items can be added with batch details."""
        movement = InventoryMovement.objects.create(
            document_no="MOV-2024-002",
            type="inbound",
            date=date.today(),
            warehouse=warehouse,
            created_by=user
        )
        
        item_line = InventoryMovementItem.objects.create(
            movement=movement,
            item=item,
            lot_number="LOT-ABC-123",
            quantity=50.00,
            mfg_date=date(2023, 12, 1),
            exp_date=date(2025, 12, 31)
        )
        
        assert item_line.movement == movement
        assert item_line.lot_number == "LOT-ABC-123"
        assert item_line.quantity == 50.00
        assert item_line.mfg_date == date(2023, 12, 1)
        assert item_line.exp_date == date(2025, 12, 31)

    def test_movement_attachment(self, user, warehouse):
        """Verify that attachments can be linked to a movement."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        movement = InventoryMovement.objects.create(
            document_no="MOV-2024-003",
            type="inbound",
            date=date.today(),
            warehouse=warehouse,
            created_by=user
        )
        
        fake_file = SimpleUploadedFile("invoice.pdf", b"file_content", content_type="application/pdf")
        
        attachment = InventoryMovementAttachment.objects.create(
            movement=movement,
            document_file=fake_file,
            created_by=user
        )
        
        assert attachment.movement == movement
        assert attachment.file_name == "invoice.pdf"
        assert attachment.created_by == user
