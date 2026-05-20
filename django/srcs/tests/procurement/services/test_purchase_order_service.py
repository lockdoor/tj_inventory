import pytest
from django.contrib.auth import get_user_model
from procurement.services.purchase_order_service import PurchaseOrderService
from procurement.models import PurchaseOrder, PurchaseOrderItem
from partners.models import Partner
from catalog.models import Item, Category

User = get_user_model()

@pytest.mark.django_db
class TestPurchaseOrderService:

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='svcuser', password='password')

    @pytest.fixture
    def partner(self, user):
        return Partner.objects.create(name="Service Supplier", code="SVC-SUPP", is_supplier=True, created_by=user)

    @pytest.fixture
    def item(self, user):
        cat = Category.objects.create(name="Test Cat", code="TC", created_by=user)
        return Item.objects.create(sku="SVC-ITEM", name="Service Item", unit="pcs", category=cat, created_by=user)

    def test_create_po_with_items(self, user, partner, item):
        items_data = [
            {'item': item, 'order_qty': 100, 'unit_cost': 10.5}
        ]
        po = PurchaseOrderService.create(
            document_no="PO-SVC-001",
            partner=partner,
            user=user,
            items=items_data
        )
        assert po.document_no == "PO-SVC-001"
        assert po.items.count() == 1
        assert po.items.first().order_qty == 100

    def test_soft_delete_restriction(self, user, partner):
        po = PurchaseOrderService.create(
            document_no="PO-DELETE",
            partner=partner,
            user=user
        )
        # Change status to Submitted
        po.status = PurchaseOrder.Status.SUBMITTED
        po.save()

        with pytest.raises(Exception) as excinfo:
            PurchaseOrderService.soft_delete(po, user=user)
        assert "Only Draft or Cancelled POs can be deleted" in str(excinfo.value)

    def test_revert_to_draft_with_arrivals(self, user, partner):
        from procurement.models import Arrival
        from inventory.models import Warehouse
        from django.core.exceptions import ValidationError
        
        po = PurchaseOrderService.create(
            document_no="PO-REVERT",
            partner=partner,
            user=user
        )
        PurchaseOrderService.submit(po, user=user)
        
        warehouse = Warehouse.objects.create(name="Test WH", code="WH1", created_by=user)
        
        # Create an arrival linked to the PO
        Arrival.objects.create(
            document_no="ARR-001",
            partner=partner,
            warehouse=warehouse,
            expected_date="2026-05-19",
            purchase_order=po,
            created_by=user
        )
        
        # Reverting to draft should fail
        with pytest.raises(ValidationError) as excinfo:
            PurchaseOrderService.revert_to_draft(po, user=user)
        
        assert "Cannot revert to draft because this Purchase Order has scheduled or received arrivals" in str(excinfo.value)

    def test_soft_delete_success_no_arrivals(self, user, partner):
        po = PurchaseOrderService.create(
            document_no="PO-DEL-OK",
            partner=partner,
            user=user
        )
        assert not po.is_deleted
        
        PurchaseOrderService.soft_delete(po, user=user)
        
        po.refresh_from_db()
        assert po.is_deleted
        assert po.updated_by == user

    def test_soft_delete_fails_with_active_arrivals(self, user, partner):
        from procurement.models import Arrival
        from inventory.models import Warehouse
        from django.core.exceptions import ValidationError

        po = PurchaseOrderService.create(
            document_no="PO-DEL-FAIL",
            partner=partner,
            user=user
        )
        warehouse = Warehouse.objects.create(name="Test WH 2", code="WH2", created_by=user)
        
        # Link an arrival to the PO
        Arrival.objects.create(
            document_no="ARR-002",
            partner=partner,
            warehouse=warehouse,
            expected_date="2026-05-20",
            purchase_order=po,
            created_by=user
        )

        with pytest.raises(ValidationError) as excinfo:
            PurchaseOrderService.soft_delete(po, user=user)
        
        assert "Cannot delete Purchase Order because it has scheduled or received arrivals" in str(excinfo.value)
