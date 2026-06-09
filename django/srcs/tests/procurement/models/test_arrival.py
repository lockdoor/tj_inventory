import pytest
from django.contrib.auth import get_user_model
from procurement.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from procurement.models.arrival import Arrival, ArrivalItem
from partners.models.partner import Partner
from catalog.models import Item, Category
from inventory.models import Warehouse
from datetime import date

User = get_user_model()

@pytest.mark.django_db
class TestArrivalModel:
    """
    Unit tests for the Arrival and ArrivalItem models.
    """

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='arrivaluser', password='password')

    @pytest.fixture
    def partner(self, user):
        return Partner.objects.create(name="Supplier B", code="SUPP-B", is_supplier=True, created_by=user)

    @pytest.fixture
    def warehouse(self, user):
        return Warehouse.objects.create(name="Secondary Wharf", code="WH-SEC", created_by=user)

    @pytest.fixture
    def category(self, user):
        return Category.objects.create(name="Hardware", code="HW", created_by=user)

    @pytest.fixture
    def item(self, user, category):
        return Item.objects.create(sku="HW-001", name="Bolt", unit="pcs", category=category, created_by=user)

    @pytest.fixture
    def po(self, user, partner):
        return PurchaseOrder.objects.create(document_no="PO-TEST-001", partner=partner, created_by=user)

    @pytest.fixture
    def po_item(self, po, item):
        return PurchaseOrderItem.objects.create(purchase_order=po, item=item, order_qty=500)

    def test_arrival_creation(self, user, partner, warehouse, po):
        """Verify that an arrival can be created with required fields."""
        arrival = Arrival.objects.create(
            document_no="ARR-2024-001",
            purchase_order=po,
            partner=partner,
            warehouse=warehouse,
            expected_date=date(2024, 7, 1),
            created_by=user
        )
        assert arrival.document_no == "ARR-2024-001"
        assert arrival.purchase_order == po
        assert arrival.warehouse == warehouse
        assert str(arrival) == "ARR-2024-001 (Supplier B)"

    def test_standalone_arrival(self, user, partner, warehouse):
        """Verify that an arrival can exist without a PO."""
        arrival = Arrival.objects.create(
            document_no="ARR-STANDALONE",
            partner=partner,
            warehouse=warehouse,
            expected_date=date(2024, 8, 1),
            created_by=user
        )
        assert arrival.purchase_order is None
        assert arrival.document_no == "ARR-STANDALONE"

    def test_arrival_item_creation(self, user, partner, warehouse, item, po_item):
        """Verify that arrival items can be created and linked to PO items."""
        arrival = Arrival.objects.create(
            document_no="ARR-ITEMS",
            partner=partner,
            warehouse=warehouse,
            expected_date=date(2024, 7, 1),
            created_by=user
        )
        arrival_line = ArrivalItem.objects.create(
            arrival=arrival,
            item=item,
            po_item=po_item,
            expected_qty=100,
            received_qty=95,
            created_by=user
        )
        assert arrival_line.arrival == arrival
        assert arrival_line.po_item == po_item
        assert arrival_line.expected_qty == 100
        assert arrival_line.received_qty == 95
        assert "ARR-ITEMS - HW-001" in str(arrival_line)

    def test_audit_fields(self, user, partner, warehouse):
        """Verify that AuditableMixin tracks metadata for Arrival."""
        arrival = Arrival.objects.create(
            document_no="ARR-AUDIT",
            partner=partner,
            warehouse=warehouse,
            expected_date=date(2024, 7, 1),
            created_by=user
        )
        assert arrival.created_by == user
        assert arrival.created_at is not None
        assert arrival.version == 1
