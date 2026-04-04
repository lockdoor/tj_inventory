import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from inventory.models import Warehouse

User = get_user_model()

@pytest.mark.django_db
class TestWarehouseModel:
    """
    Unit tests for the Warehouse model.
    """

    @pytest.fixture
    def user(self):
        """Standard user for audit fields."""
        return User.objects.create_user(username='testuser', password='password')

    def test_warehouse_creation(self, user):
        """Verify that a warehouse can be created with required fields."""
        warehouse = Warehouse.objects.create(
            name="Main Warehouse",
            code="WH-001",
            created_by=user
        )
        assert str(warehouse) == "WH-001 - Main Warehouse"
        assert warehouse.status == "active"
        assert warehouse.code == "WH-001"
        assert warehouse.name == "Main Warehouse"

    def test_warehouse_code_normalization(self, user):
        """Verify that warehouse code is normalized to uppercase and stripped."""
        warehouse = Warehouse.objects.create(
            name="  Global Hub  ",
            code="  wh-gh  ",
            created_by=user
        )
        assert warehouse.code == "WH-GH"
        assert warehouse.name == "Global Hub"

    def test_duplicate_code_fails(self, user):
        """Verify that creating two warehouses with the same code raises IntegrityError."""
        Warehouse.objects.create(
            name="Warehouse A",
            code="WH-ABC",
            created_by=user
        )
        with pytest.raises(IntegrityError):
            Warehouse.objects.create(
                name="Warehouse B",
                code="WH-ABC", # Duplicate code
                created_by=user
            )

    def test_status_choices(self, user):
        """Verify that status can be set to inactive."""
        warehouse = Warehouse.objects.create(
            name="Old Warehouse",
            code="WH-OLD",
            status="inactive",
            created_by=user
        )
        assert warehouse.status == "inactive"

    def test_audit_fields(self, user):
        """Verify that audit mixin tracks creation metadata."""
        warehouse = Warehouse.objects.create(
            name="Audit Test",
            code="WH-AUDIT",
            created_by=user
        )
        assert warehouse.created_by == user
        assert warehouse.created_at is not None
        assert warehouse.updated_at is not None
        assert warehouse.updated_by is None # No update yet
