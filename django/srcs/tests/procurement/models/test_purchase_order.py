import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from procurement.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from partners.models.partner import Partner
from catalog.models import Item, Category
from inventory.models import Warehouse
from procurement.models.arrival import Arrival, ArrivalItem
from datetime import date

User = get_user_model()

@pytest.mark.django_db
class TestPurchaseOrderModel:
    """
    Unit tests for the PurchaseOrder and PurchaseOrderItem models.
    """

    @pytest.fixture
    def user(self):
        """Standard user for audit fields."""
        return User.objects.create_user(username='procureuser', password='password')

    @pytest.fixture
    def partner(self, user):
        """Standard supplier partner."""
        return Partner.objects.create(
            name="Supplier A",
            code="SUPP-A",
            is_supplier=True,
            created_by=user
        )

    @pytest.fixture
    def category(self, user):
        """Standard category."""
        return Category.objects.create(
            name="Raw Materials",
            code="RAW",
            created_by=user
        )

    @pytest.fixture
    def item(self, user, category):
        """Standard item."""
        return Item.objects.create(
            sku="MAT-001",
            name="Steel Plate",
            unit="pcs",
            category=category,
            created_by=user
        )

    def test_purchase_order_creation(self, user, partner):
        """Verify that a purchase order can be created with required fields."""
        po = PurchaseOrder.objects.create(
            document_no="PO-2024-001",
            partner=partner,
            expected_date=date(2024, 6, 1),
            status=PurchaseOrder.Status.DRAFT,
            created_by=user
        )
        assert po.document_no == "PO-2024-001"
        assert po.partner == partner
        assert po.status == PurchaseOrder.Status.DRAFT
        assert str(po) == "PO-2024-001 (Supplier A)"

    def test_document_no_uniqueness(self, user, partner):
        """Verify that document_no must be unique."""
        PurchaseOrder.objects.create(
            document_no="UNIQUE-PO",
            partner=partner,
            created_by=user
        )
        with pytest.raises(IntegrityError):
            PurchaseOrder.objects.create(
                document_no="UNIQUE-PO",
                partner=partner,
                created_by=user
            )

    def test_audit_fields(self, user, partner):
        """Verify that AuditableMixin tracks metadata."""
        po = PurchaseOrder.objects.create(
            document_no="AUDIT-PO",
            partner=partner,
            created_by=user
        )
        assert po.created_by == user
        assert po.created_at is not None
        assert po.version == 1
        
        # Test optimistic locking/versioning on update
        po.note = "Updated note"
        po.save()
        assert po.version == 2

    def test_purchase_order_item_creation(self, user, partner, item):
        """Verify that items can be added to a purchase order."""
        po = PurchaseOrder.objects.create(
            document_no="PO-ITEMS",
            partner=partner,
            created_by=user
        )
        item_line = PurchaseOrderItem.objects.create(
            purchase_order=po,
            item=item,
            order_qty=100.00,
            unit_cost=15.50
        )
        assert item_line.purchase_order == po
        assert item_line.item == item
        assert item_line.order_qty == 100.00
        assert item_line.unit_cost == 15.50
        assert "PO-ITEMS - MAT-001" in str(item_line)
        assert "100" in str(item_line)

    def test_cascade_delete(self, user, partner, item):
        """Verify that deleting a PO deletes its items."""
        po = PurchaseOrder.objects.create(
            document_no="DELETE-ME",
            partner=partner,
            created_by=user
        )
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            item=item,
            order_qty=10
        )
        assert PurchaseOrderItem.objects.filter(purchase_order=po).count() == 1
        
        po_id = po.id
        po.hard_delete()
        assert PurchaseOrderItem.objects.filter(purchase_order_id=po_id).count() == 0

    def test_purchase_order_item_arrival_qty(self, user, partner, item):
        """Verify that arrival_qty on PurchaseOrderItem correctly sums non-cancelled arrivals."""
        # Create a warehouse for arrivals
        warehouse = Warehouse.objects.create(
            name="Main Warehouse",
            code="WH-MAIN",
            created_by=user
        )
        
        po = PurchaseOrder.objects.create(
            document_no="PO-ARRIVAL-TEST",
            partner=partner,
            created_by=user
        )
        
        po_line = PurchaseOrderItem.objects.create(
            purchase_order=po,
            item=item,
            order_qty=100
        )
        
        # Initially, arrival_qty should be 0
        assert po_line.arrival_qty == 0
        
        # Create an active scheduled arrival
        arrival1 = Arrival.objects.create(
            document_no="ARR-ACTIVE-1",
            purchase_order=po,
            partner=partner,
            warehouse=warehouse,
            expected_date=date(2026, 6, 1),
            status=Arrival.Status.SCHEDULED,
            created_by=user
        )
        ArrivalItem.objects.create(
            arrival=arrival1,
            item=item,
            po_item=po_line,
            expected_qty=40,
            created_by=user
        )
        
        # Refreshed po_line should show 40
        assert po_line.arrival_qty == 40
        
        # Create an active received arrival
        arrival2 = Arrival.objects.create(
            document_no="ARR-ACTIVE-2",
            purchase_order=po,
            partner=partner,
            warehouse=warehouse,
            expected_date=date(2026, 6, 2),
            status=Arrival.Status.RECEIVED,
            created_by=user
        )
        ArrivalItem.objects.create(
            arrival=arrival2,
            item=item,
            po_item=po_line,
            expected_qty=35,
            created_by=user
        )
        
        # Refreshed po_line should show 40 + 35 = 75
        assert po_line.arrival_qty == 75
        
        # Create a cancelled arrival (should be excluded)
        arrival_cancelled = Arrival.objects.create(
            document_no="ARR-CANCELLED",
            purchase_order=po,
            partner=partner,
            warehouse=warehouse,
            expected_date=date(2026, 6, 3),
            status=Arrival.Status.CANCELLED,
            created_by=user
        )
        ArrivalItem.objects.create(
            arrival=arrival_cancelled,
            item=item,
            po_item=po_line,
            expected_qty=100,
            created_by=user
        )
        
        # Refreshed po_line should still show 75 (cancelled shipment is excluded)
        assert po_line.arrival_qty == 75

        # Create a soft-deleted arrival (should be excluded)
        arrival_deleted = Arrival.objects.create(
            document_no="ARR-DELETED",
            purchase_order=po,
            partner=partner,
            warehouse=warehouse,
            expected_date=date(2026, 6, 4),
            status=Arrival.Status.SCHEDULED,
            is_deleted=True,
            created_by=user
        )
        ArrivalItem.objects.create(
            arrival=arrival_deleted,
            item=item,
            po_item=po_line,
            expected_qty=150,
            created_by=user
        )
        
        # Refreshed po_line should still show 75 (deleted shipment is excluded)
        assert po_line.arrival_qty == 75
